"""Keep historical source verification valid as the working tree evolves."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import report_write_diagnostics_findings as findings


class WriteDiagnosticsFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = json.loads((findings.ROOT / 'evidence/write-diagnostics' /
                               findings.FULL / 'results.json').read_text())

    def test_original_archives_and_measured_source_validate(self):
        pilot, _ = findings.load(findings.PILOT, 'pilot')
        full, _ = findings.load(findings.FULL, 'full')
        self.assertEqual(len(pilot['trials']), 30)
        self.assertEqual(len(full['trials']), 150)
        self.assertEqual(len(findings.statistics(findings.observations(full))), 30)

    def test_archive_works_without_git_or_current_measured_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'provenance/write-diagnostics'
            shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
            # Current development is deliberately different from measured code.
            (root / 'Dockerfile').write_text('FROM a-different-future-base\n')
            self.assertFalse((root / '.git').exists())
            with patch.object(findings, 'ROOT', root), patch.object(findings, 'SOURCE_SNAPSHOT', snapshot):
                findings.check_source(self.full['source_sha256'], 'host')
                findings.check_source(self.full['trials'][0]['prepare']['source_sha256'], 'worker')

    def test_snapshot_and_manifest_cannot_replace_archived_fingerprints(self):
        for change_manifest in (False, True):
            with self.subTest(change_manifest=change_manifest), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot'
                shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
                path = snapshot / 'source/Dockerfile'
                raw = path.read_bytes() + b'# changed historical source\n'
                path.write_bytes(raw)
                if change_manifest:
                    manifest = json.loads((snapshot / 'manifest.json').read_text())
                    manifest['files']['Dockerfile'] = {
                        'sha256_lf': hashlib.sha256(raw).hexdigest(),
                        'sha256_crlf': hashlib.sha256(raw.replace(b'\n', b'\r\n')).hexdigest(),
                        'git_blob_sha1': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                    }
                    (snapshot / 'manifest.json').write_text(json.dumps(manifest))
                with patch.object(findings, 'SOURCE_SNAPSHOT', snapshot):
                    with self.assertRaisesRegex(ValueError, 'Measured source'):
                        findings.check_source(self.full['trials'][0]['prepare']['source_sha256'], 'worker')

    def test_changed_or_missing_recorded_source_is_rejected(self):
        original = self.full['trials'][0]['prepare']['source_sha256']
        for change in ('digest', 'missing'):
            recorded = dict(original)
            if change == 'digest':
                recorded['Dockerfile'] = '0' * 64
            else:
                del recorded['Dockerfile']
            with self.subTest(change=change), self.assertRaises(ValueError):
                findings.check_source(recorded, 'worker')

    def test_snapshot_allows_checkout_line_endings_but_not_wrong_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'snapshot'
            shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
            for path in (snapshot / 'source').rglob('*'):
                if path.is_file():
                    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            with patch.object(findings, 'SOURCE_SNAPSHOT', snapshot):
                findings.check_source(self.full['source_sha256'], 'host')
                findings.check_source(self.full['trials'][0]['prepare']['source_sha256'], 'worker')
                manifest = json.loads((snapshot / 'manifest.json').read_text())
                manifest['revision'] = '0' * 40
                (snapshot / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(ValueError, 'snapshot'):
                    findings.check_source(self.full['source_sha256'], 'host')

    def test_changed_measurements_still_fail_validation(self):
        result = copy.deepcopy(self.full)
        result['trials'][0]['verify']['verified_final_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            findings.validate(result, findings.FULL, 'full')

    def test_tampered_source_rejected_before_output_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'snapshot'
            shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
            (snapshot / 'source/Dockerfile').write_text('FROM modified\n')
            output = root / 'generated'
            with patch.object(findings, 'SOURCE_SNAPSHOT', snapshot):
                with self.assertRaisesRegex(ValueError, 'Measured source snapshot changed'):
                    findings.build(output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
