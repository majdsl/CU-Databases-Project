import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from benchmarks.telemetry import parse_stat, quota_cpus, snapshot, difference
from benchmarks.concurrency import run, report, CLIENTS, MODES
from benchmarks.core import Config, ENGINES


class TelemetryTests(unittest.TestCase):
    def state(self, wall, usage, periods, throttled, process):
        return {'wall_ns': wall, 'process_cpu_ns': process, 'cpu_max': '100000 100000',
                'cpu_stat': {'usage_usec': usage, 'nr_periods': periods, 'nr_throttled': throttled}}

    def test_counter_units_and_deltas(self):
        before = self.state(1_000_000_000, 200000, 10, 2, 100000000)
        after = self.state(3_000_000_000, 1700000, 30, 7, 1100000000)
        d = difference(before, after)
        self.assertEqual(d['cgroup_average_cores'], .75)
        self.assertEqual(d['process_average_cores'], .5)
        self.assertEqual(d['counter_delta']['nr_throttled'], 5)
        self.assertEqual(d['counter_delta']['nr_periods'], 20)

    def test_missing_data_is_not_zero_throttling(self):
        before = self.state(1, 0, 0, 0, 0)
        after = self.state(1000001, 0, 0, 0, 0)
        after['unavailable_reason'] = 'FileNotFoundError'
        d = difference(before, after)
        self.assertEqual(d['cgroup_status'], 'unavailable')
        self.assertNotIn('counter_delta', d)

    def test_reset_and_quota_change_not_reported_as_valid(self):
        before = self.state(1, 200, 20, 4, 0)
        after = self.state(1000001, 100, 10, 2, 0)
        self.assertEqual(difference(before, after)['cgroup_status'], 'counter_reset')
        after['cpu_max'] = '200000 100000'
        self.assertEqual(difference(before, after)['cgroup_status'], 'quota_changed')

    def test_parsing_and_invalid_counters(self):
        self.assertEqual(parse_stat('usage_usec 300\nnr_throttled 2\nnew_field 42')['nr_throttled'], 2)
        for text in ('usage_usec -1', 'usage_usec abc', 'nr_throttled 2', 'usage_usec 1\nusage_usec 2'):
            with self.assertRaises(ValueError):
                parse_stat(text)
        self.assertEqual(quota_cpus('200000 100000'), 2)
        self.assertIsNone(quota_cpus('max 100000'))
        for text in ('0 100000', '100000 0', 'n/a'):
            with self.assertRaises(ValueError):
                quota_cpus(text)

    def test_snapshot_handles_missing_cgroup_files(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn('unavailable_reason', snapshot(Path(directory)))
            (Path(directory) / 'cpu.stat').write_text('usage_usec 100\nnr_throttled 0\n')
            (Path(directory) / 'cpu.max').write_text('100000 100000')
            self.assertEqual(snapshot(Path(directory))['quota_cpus'], 1)

    def test_wrong_quota_rejected_before_database_connection(self):
        with patch.dict('os.environ', {'DB_NAME': 'engine_lab'}), \
             patch('benchmarks.concurrency.runtime_metadata', return_value={'cgroup_cpu_max': '100000 100000'}), \
             patch('benchmarks.concurrency.connect') as connection:
            with self.assertRaisesRegex(ValueError, 'CPU quota differs'):
                run(Config(), 1000, None, expected_runner_cpus=2)
            connection.assert_not_called()

    def test_cpu_report_marks_unavailable_observations(self):
        trials = [{'engine': e, 'mode': m, 'clients': n, 'updates_per_second': 100,
                   'runner_cpu': {'cgroup_status': 'unavailable'}}
                  for e in ENGINES for m in MODES for n in CLIENTS for _ in range(5)]
        text = report({'status': 'completed', 'format_version': 2, 'run_id': 'unit-only',
                       'config': {'rounds': 5}, 'trials': trials})
        self.assertIn('| unavailable | 0/0 |', text)
        self.assertIn('runner only', text)
