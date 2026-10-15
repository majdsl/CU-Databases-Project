import threading
import unittest
from collections import Counter
from unittest.mock import MagicMock, patch

from benchmarks.concurrency import streams, expected_rows, execute_workers, report, run, trial
from benchmarks.core import Config, generate_rows


class FakeConnection:
    def __init__(self, counts, lock, fail=False):
        self.counts, self.lock, self.fail = counts, lock, fail
        self.rowcount = 1
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def cursor(self):
        return self
    def execute(self, sql, params=None):
        if sql.startswith('UPDATE'):
            if self.fail:
                raise ConnectionError('simulated disconnect')
            with self.lock:
                self.counts[params[0]] += 1


class ConcurrencyTests(unittest.TestCase):
    def test_same_total_work_and_key_frequencies_at_all_client_counts(self):
        for mode in ('disjoint', 'hotspot'):
            reference = Counter(streams(10000, 1000, 1, mode)[0])
            for clients in (1, 2, 4):
                keys = streams(10000, 1000, clients, mode)
                self.assertEqual(Counter(k for s in keys for k in s), reference)
                self.assertEqual(sum(map(len, keys)), 1000)
                if mode == 'disjoint':
                    for i, stream in enumerate(keys):
                        for other in keys[i + 1:]:
                            self.assertFalse(set(stream) & set(other))

    def test_invalid_workload_rejected(self):
        for args in ((10000, 101, 4, 'hotspot'), (10000, 100, 3, 'disjoint'),
                     (10000, 100, 4, 'sql'), (2, 100, 4, 'disjoint')):
            with self.assertRaises(ValueError):
                streams(*args)

    def test_update_oracle_changes_only_expected_column(self):
        rows = generate_rows(Config(rows=100))
        actual = expected_rows(rows, [[1, 1], [1, 2]])
        self.assertEqual(actual[0][4], rows[0][4] + 3)
        self.assertEqual(actual[1][4], rows[1][4] + 1)
        self.assertEqual(actual[2:], rows[2:])
        self.assertEqual(actual[0][:4] + actual[0][5:], rows[0][:4] + rows[0][5:])

    def test_workers_preserve_all_successful_operations(self):
        counts, lock = Counter(), threading.Lock()
        keys = streams(100, 100, 4, 'hotspot')
        result = execute_workers(keys, lambda: FakeConnection(counts, lock))
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['completed'], 100)
        self.assertEqual(counts, Counter(k for s in keys for k in s))
        self.assertGreater(result['updates_per_second'], 0)

    def test_connection_failure_aborts_barrier_without_success_report(self):
        def broken():
            raise ConnectionError('simulated')
        result = execute_workers(streams(100, 100, 4, 'hotspot'), broken)
        self.assertEqual(result['status'], 'failed')
        self.assertNotIn('updates_per_second', result)

    def test_update_failure_is_not_retried(self):
        counts, lock = Counter(), threading.Lock()
        result = execute_workers(streams(100, 100, 4, 'hotspot'),
                                 lambda: FakeConnection(counts, lock, fail=True))
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['completed'], 0)
        self.assertNotIn('updates_per_second', result)

    def test_failed_or_incomplete_runs_cannot_be_summarized(self):
        with self.assertRaises(ValueError):
            report({'status': 'failed'})
        with self.assertRaises(ValueError):
            report({'status': 'completed', 'run_id': 'test', 'config': {'rounds': 5}, 'trials': []})

    def test_wrong_database_rejected_before_connecting(self):
        with patch.dict('os.environ', {'DB_NAME': 'production'}):
            with self.assertRaises(ValueError):
                run(Config(), 1000, None)

    def test_existing_table_never_dropped(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('benchmark_events',)
        config = Config(rows=100)
        with self.assertRaisesRegex(RuntimeError, 'refusing to overwrite'):
            trial(connection, 'InnoDB', config, generate_rows(config), 1, 'disjoint', 100)
        self.assertFalse(any('DROP TABLE' in str(c) for c in cursor.execute.call_args_list))

    def test_engine_substitution_refused_and_owned_table_cleaned(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [None, ('benchmark_events', 'DDL'), ('InnoDB',)]
        config = Config(rows=100)
        with self.assertRaisesRegex(RuntimeError, 'Engine substitution'):
            trial(connection, 'ROCKSDB', config, generate_rows(config), 1, 'disjoint', 100)
        cursor.execute.assert_called_with('DROP TABLE benchmark_events')
