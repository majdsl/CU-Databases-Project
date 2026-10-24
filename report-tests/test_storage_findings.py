"""Offline storage-report regression checks; run outside the lightweight DB runner."""
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class StorageFindingsTests(unittest.TestCase):
    def test_findings_reject_corrupted_evidence(self):
        from scripts import report_storage_findings as findings
        source = ROOT / 'evidence/storage' / findings.RUN / 'results.json'
        mutations = [
            ('row count', lambda t: t['load'].update(verified_rows=0)),
            ('checksum', lambda t: t['load'].update(verified_dataset_sha256='wrong')),
            ('exit code', lambda t: t['before_stop'].update(ExitCode=137)),
            ('OOM', lambda t: t['after_stop'].update(OOMKilled=True)),
            ('inventory', lambda t: t['before'].update(regular_file_allocated_bytes=-1)),
            ('delta', lambda t: t['delta'].update(regular_file_apparent_bytes=-1)),
        ]
        for name, mutate in mutations:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                result = json.loads(source.read_text(encoding='utf-8'))
                mutate(result['trials'][0])
                path = Path(directory) / 'results.json'
                path.write_text(json.dumps(result), encoding='utf-8')
                with self.assertRaises(ValueError):
                    findings.build(path, Path(directory) / 'output')
                self.assertFalse((Path(directory) / 'output').exists())


if __name__ == '__main__':
    unittest.main()
