import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from benchmarks.storage import file_snapshot, load

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('storage_host', ROOT / 'scripts/run_storage.py')
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)

class StorageTests(unittest.TestCase):
    def test_inventory_sparse_hardlinks_symlinks(self):
        if os.name != 'posix':
            self.skipTest('File inventory runs inside Linux Docker')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'normal').write_bytes(b'abc')
            with (root / 'sparse').open('wb') as stream:
                stream.seek(8 * 1024 * 1024)
                stream.write(b'x')
            os.link(root / 'normal', root / 'alias')
            (root / 'link').symlink_to('normal')
            result = file_snapshot(root)
            self.assertEqual(result['regular_file_apparent_bytes'], 8 * 1024 * 1024 + 4)
            self.assertEqual(result['regular_file_allocated_bytes'],
                ((root / 'normal').stat().st_blocks + (root / 'sparse').stat().st_blocks) * 512)
            self.assertEqual(result['skipped_nonregular_paths'], ['link'])
            self.assertEqual(sum(f['counted'] for f in result['files']), 2)

    def test_negative_delta_retained(self):
        before = dict(regular_file_apparent_bytes=100, regular_file_allocated_bytes=512)
        after = dict(regular_file_apparent_bytes=80, regular_file_allocated_bytes=0)
        self.assertEqual(host.size_delta(before, after)['regular_file_allocated_bytes'], -512)

    def test_normal_project_rejected_before_command(self):
        with patch.object(host, 'execute') as execute:
            for project in ('cu-engine-lab', 'cu-storage-test', '', 'cu-storage-' + 'a'*32 + '-1\n'):
                with self.subTest(project=project), self.assertRaises(ValueError):
                    host.compose(project, 'down', '--volumes')
            execute.assert_not_called()

    def test_existing_project_rejected(self):
        with patch.object(host, 'execute', return_value='existing'), self.assertRaises(RuntimeError):
            host.ensure_new_project('cu-storage-' + 'a'*32 + '-1')

    def test_unclean_shutdown_blocks_measurement(self):
        for state in ({'Status': 'exited', 'ExitCode': 137}, {'Status': 'running', 'ExitCode': 0},
                      {'Status': 'exited', 'ExitCode': 0, 'OOMKilled': True}):
            with patch.object(host, 'compose'), patch.object(host, 'db_state', return_value=('id', state)):
                with self.assertRaises(RuntimeError):
                    host.stop_cleanly('test')

    def test_no_snapshot_of_live_database(self):
        with patch.object(host, 'db_state', return_value=('id', {'Status': 'running', 'ExitCode': 0})), patch.object(host, 'compose') as compose:
            with self.assertRaises(RuntimeError):
                host.snapshot('test')
            compose.assert_not_called()

    def test_loader_requires_isolation(self):
        with patch.dict(os.environ, {'DB_NAME': 'engine_lab'}, clear=True), self.assertRaises(ValueError):
            load('InnoDB', 100, 1)

    def test_existing_tables_not_changed(self):
        driver = MagicMock()
        cursor = driver.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value = (1,)
        cursor.fetchall.return_value = [('existing_data',)]
        env = dict(STORAGE_EXPERIMENT='isolated-v1', DB_NAME='engine_lab', DB_HOST='db', DB_USER='benchmark', DB_PASSWORD='test-only')
        with patch.dict(os.environ, env), patch.dict('sys.modules', {'pymysql': driver}):
            with self.assertRaisesRegex(RuntimeError, 'empty engine_lab'):
                load('InnoDB', 100, 1)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertFalse(any('CREATE' in s or 'DROP' in s or 'INSERT' in s for s in statements))

    def test_failed_trial_preserves_evidence_and_volume(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('.env', 'scripts/run_storage.py', 'compose.storage.yaml', 'benchmarks/storage.py'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            def fake_compose(project, *args, **kwargs):
                if args[0] == 'up':
                    raise RuntimeError('simulated startup failure')
            with patch.object(host, 'ROOT', root), patch.object(host, 'execute', return_value='linux'), patch.object(host, 'ensure_new_project'), patch.object(host, 'compose', side_effect=fake_compose) as compose:
                with self.assertRaisesRegex(RuntimeError, 'startup failure'):
                    host.run(SimpleNamespace(rows=100, seed=1, pilot=True, power_condition='test'))
            path = next((root / 'results').glob('*/results.json'))
            result = json.loads(path.read_text())
            self.assertEqual(result['status'], 'failed')
            self.assertIn('active_project', result)
            self.assertFalse(path.with_name('summary.md').exists())
            self.assertFalse(any('down' in call.args for call in compose.call_args_list))

    def test_incomplete_report_rejected(self):
        with self.assertRaises(ValueError):
            host.render_report({'status': 'failed'})
        with self.assertRaises(ValueError):
            host.render_report(dict(status='completed', rounds=1, trials=[]))

    def test_memory_and_disk_are_distinguished(self):
        result = dict(status='completed', rounds=1, pilot=True, run_id='test', rows=100, trials=[])
        for engine in host.ENGINES:
            sizes = dict(regular_file_apparent_bytes=10, regular_file_allocated_bytes=512)
            result['trials'].append(dict(engine=engine, round=1, before=sizes, after=sizes,
                delta=host.size_delta(sizes, sizes), load={'live_engine_reported_table_status': dict(Data_length=10, Index_length=20)}))
        report = host.render_report(result)
        self.assertIn('MEMORY loses its rows at shutdown', report)
        self.assertIn('Approximate RAM allocation', report)
        self.assertIn('not table-only size', report)

if __name__ == '__main__':
    unittest.main()
