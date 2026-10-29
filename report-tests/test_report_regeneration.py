"""The complete documented reporting path must work from current source, offline."""
from pathlib import Path, PurePosixPath, PureWindowsPath
import tempfile
import unittest

from scripts import check_reports


class ReportRegenerationTests(unittest.TestCase):
    def test_output_names_match_report_manifest_on_windows_and_posix(self):
        for kind, root in ((PureWindowsPath, 'C:/scratch/docs'), (PurePosixPath, '/scratch/docs')):
            with self.subTest(platform=kind.__name__):
                directory = kind(root)
                for names in check_reports.REPORTS.values():
                    for name in names:
                        self.assertEqual(check_reports.output_name(directory/name, directory), name)

    def test_all_eight_current_reports_regenerate_without_changing_inputs(self):
        result = check_reports.regenerate(repeat=True)
        self.assertEqual(result['reports'], 8)
        self.assertEqual(result['outputs'], 55)
        self.assertGreaterEqual(result['evidence_files'], 824)
        self.assertEqual(result['optimization'], __import__('sys').flags.optimize)

    def test_snapshot_uses_current_files_and_excludes_local_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, target = root/'source', root/'scratch'
            (source/'scripts').mkdir(parents=True)
            (source/'scripts/report_cpu.py').write_text('# current uncommitted edit\n')
            (source/'.env').write_text('PRIVATE=do-not-copy\n')
            (source/'scripts/.env').write_text('PRIVATE=do-not-copy\n')
            (source/'scripts/__pycache__').mkdir()
            (source/'scripts/__pycache__/old.pyc').write_bytes(b'stale')
            (source/'results').mkdir()
            (source/'results/private.json').write_text('{}')
            (source/'.git').mkdir()
            (source/'.git/config').write_text('private git configuration')
            paths = check_reports.copy_inputs(source, target)
            self.assertEqual(paths, [Path('scripts/report_cpu.py')])
            self.assertEqual((target/'scripts/report_cpu.py').read_text(), '# current uncommitted edit\n')
            self.assertEqual([p.relative_to(target) for p in target.rglob('*') if p.is_file()], paths)

    def test_missing_dataset_explains_the_verified_fetch_prerequisite(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, 'scripts/fetch_openflights.py'):
                check_reports.regenerate(Path(temporary))

    def test_changed_statistic_is_rejected_with_location(self):
        with self.assertRaisesRegex(ValueError, 'Changed number at JSON.statistics.mean'):
            check_reports.same_json({'statistics': {'mean': 1.1}}, {'statistics': {'mean': 1.0}})
        check_reports.same_json({'statistics': {'mean': 1.0+1e-16}}, {'statistics': {'mean': 1.0}})


if __name__ == '__main__':
    unittest.main()
