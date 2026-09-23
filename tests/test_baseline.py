import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from benchmarks.core import Config, ENGINES, dataset_digest, describe, engine_schedule, expected_scan, generate_rows, lookup_ids
from benchmarks.report import markdown, summarize
from benchmarks.run import run, save_json, trial, verify_rows


class RowsCursor:
    def __init__(self, rows):
        self.rows = list(rows)

    def execute(self, *args):
        pass

    def fetchmany(self, size):
        batch, self.rows = self.rows[:size], self.rows[size:]
        return batch


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.config = Config(rows=100, lookups=10, scans=2)

    def test_deterministic_dataset_and_fingerprint(self):
        rows = generate_rows(self.config)
        self.assertEqual(rows, generate_rows(self.config))
        self.assertNotEqual(dataset_digest(rows), dataset_digest(generate_rows(Config(rows=100, seed=12))))
        self.assertEqual([r[0] for r in rows], list(range(1, 101)))
        self.assertTrue(all(len(r[6]) == 64 and 1 <= r[1] <= 500 for r in rows))

    def test_scan_oracle_has_known_answer(self):
        rows = [(1, 1, 0, -5, 100, 2, 'a'), (2, 1, 0, 10, 250, 3, 'b')]
        self.assertEqual(expected_scan(rows), (2, 5, 950))

    def test_schedule_balances_every_position(self):
        for seed in (0, 1, 15):
            schedule = engine_schedule(seed, 10)
            for block in (schedule[:5], schedule[5:]):
                for position in range(5):
                    self.assertEqual(set(row[position] for row in block), set(ENGINES))
            self.assertEqual(schedule, engine_schedule(seed, 10))

    def test_invalid_workload_rejected(self):
        for kwargs in ({'rows': 99}, {'rows': 200001}, {'rounds': 3},
                       {'scans': 1}, {'lookups': 0}, {'batch_size': 0}, {'rows': True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Config(**kwargs).validate()

    def test_lookup_stream_is_reproducible_and_in_range(self):
        ids = lookup_ids(42, 0, 100, 200)
        self.assertEqual(ids, lookup_ids(42, 0, 100, 200))
        self.assertNotEqual(ids, lookup_ids(42, 1, 100, 200))
        self.assertTrue(all(1 <= key <= 100 for key in ids))

    def test_statistics_known_values(self):
        stats = describe([1, 2, 3, 4, 5])
        self.assertEqual(stats['mean'], 3)
        self.assertAlmostEqual(stats['sample_sd'], math.sqrt(2.5))
        self.assertEqual(describe(list(range(1, 101)))['p95_nearest_rank'], 95)
        self.assertIsNone(describe([1])['sample_sd'])
        for invalid in ([], [float('nan')], [-1]):
            with self.assertRaises(ValueError):
                describe(invalid)

    def test_row_validation_detects_corruption_missing_and_extra_rows(self):
        expected = generate_rows(self.config)
        self.assertEqual(verify_rows(RowsCursor(expected), expected), dataset_digest(expected))
        wrong = [list(row) for row in expected]
        wrong[50][4] += 1
        for rows in (wrong, expected[:-1], expected + [expected[-1]]):
            with self.assertRaises(RuntimeError):
                verify_rows(RowsCursor(rows), expected)

    def test_summary_weights_rounds_equally(self):
        trials = [{'engine': 'InnoDB', 'load_seconds': 1, 'lookup_ms': [1]*100, 'scan_ms': [2, 2]},
                  {'engine': 'InnoDB', 'load_seconds': 3, 'lookup_ms': [9], 'scan_ms': [6, 6]}]
        row = next(r for r in summarize(trials) if r['metric'] == 'point_lookup')
        self.assertEqual(row['n'], 2)
        self.assertEqual(row['mean'], 5)
        self.assertAlmostEqual(row['sample_sd'], math.sqrt(32))

    def test_partial_runs_cannot_be_reported_as_complete(self):
        with self.assertRaises(ValueError):
            markdown({'status': 'failed'})

    def test_wrong_database_is_rejected_before_connection(self):
        with patch.dict('os.environ', {'DB_NAME': 'production'}), self.assertRaises(ValueError):
            run(self.config, Path('/unused'))

    def test_existing_table_is_never_dropped(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = ('benchmark_events',)
        with self.assertRaisesRegex(RuntimeError, 'refusing to overwrite'):
            trial(connection, 'InnoDB', self.config, [], 0)
        self.assertFalse(any('DROP TABLE' in str(call) for call in cursor.execute.call_args_list))

    def test_silent_engine_substitution_fails_and_cleans_up_owned_table(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = [None, ('InnoDB',)]
        with self.assertRaisesRegex(RuntimeError, 'Engine substitution'):
            trial(connection, 'ROCKSDB', self.config, [], 0)
        cursor.execute.assert_called_with('DROP TABLE benchmark_events')

    def test_complete_report_labels_statistical_unit(self):
        trials = [{'engine': e, 'load_seconds': 1, 'lookup_ms': [2, 3], 'scan_ms': [4, 5]}
                  for e in ENGINES for _ in range(5)]
        report = markdown({'status': 'completed', 'run_id': 'unit-test-not-a-real-run',
                           'config': {'rows': 100, 'rounds': 5}, 'trials': trials})
        self.assertIn('per-round query means', report)
        self.assertIn('not independent machine replications', report)
        self.assertEqual(report.count('| ROCKSDB |'), 3)

    def test_all_engine_schemas_have_same_columns_and_indexes(self):
        directory = Path(__file__).resolve().parents[1] / 'sql/benchmark'
        definitions = []
        for engine in ENGINES:
            ddl = (directory / (engine.lower() + '.sql')).read_text()
            prefix, suffix = ddl.split('ENGINE=')
            definitions.append(prefix)
            self.assertEqual(suffix.split()[0].lower(), engine.lower())
        self.assertEqual(len(set(definitions)), 1)

    def test_json_checkpoint_replaces_previous_valid_file(self):
        import json
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'results.json'
            save_json(path, {'status': 'running'})
            save_json(path, {'status': 'failed', 'trials': [1]})
            self.assertEqual(json.loads(path.read_text()), {'status': 'failed', 'trials': [1]})
            self.assertFalse(path.with_suffix('.tmp').exists())


if __name__ == '__main__':
    unittest.main()
