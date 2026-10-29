"""Historical cache reporting must survive source evolution without trusting tampering."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import report_cache_pressure_findings as findings


class CachePressureFindingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full = json.loads((findings.ROOT / 'evidence/cache-pressure' /
                               findings.FULL / 'results.json').read_text())

    def test_archived_host_and_every_worker_source_validate(self):
        for run, mode, count in ((findings.PILOT, 'pilot', 2), (findings.FULL, 'full', 12)):
            result, _, workers = findings.load(run, mode)
            self.assertEqual(len(result['trials']), count)
            self.assertEqual(len(workers), count)

    def test_source_archive_needs_no_git_or_current_measured_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'provenance/cache-pressure'
            shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
            (root / 'compose.cache-pressure.yaml').write_text('future: pinned-images\n')
            self.assertFalse((root / '.git').exists())
            with patch.object(findings, 'ROOT', root), patch.object(findings, 'SOURCE_SNAPSHOT', snapshot):
                findings.check_source(self.full['source_sha256'], 'host')
                findings.check_source(self.full['trials'][0]['source_sha256'], 'worker')

    def test_changed_snapshot_even_with_matching_modified_manifest_rejected(self):
        for rewrite_manifest in (False, True):
            with self.subTest(rewrite_manifest=rewrite_manifest), tempfile.TemporaryDirectory() as directory:
                snapshot = Path(directory) / 'snapshot'
                shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
                name = 'scripts/run_cache_pressure.py'
                raw = (snapshot / 'source' / name).read_bytes() + b'# tampered measured source\n'
                (snapshot / 'source' / name).write_bytes(raw)
                if rewrite_manifest:
                    manifest = json.loads((snapshot / 'manifest.json').read_text())
                    manifest['files'][name] = dict(
                        git_blob_sha1=hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest(),
                        sha256_lf=hashlib.sha256(raw).hexdigest(),
                        sha256_crlf=hashlib.sha256(raw.replace(b'\n', b'\r\n')).hexdigest())
                    (snapshot / 'manifest.json').write_text(json.dumps(manifest))
                with patch.object(findings, 'SOURCE_SNAPSHOT', snapshot), self.assertRaises(ValueError):
                    findings.check_source(self.full['source_sha256'], 'host')

    def test_missing_wrong_or_extra_archived_fingerprint_rejected(self):
        for role, original in (('host', self.full['source_sha256']),
                               ('worker', self.full['trials'][0]['source_sha256'])):
            for change in ('missing', 'wrong', 'extra'):
                recorded = dict(original)
                key = next(iter(recorded))
                if change == 'missing':
                    del recorded[key]
                elif change == 'wrong':
                    recorded[key] = '0' * 64
                else:
                    recorded['../outside'] = '0' * 64
                with self.subTest(role=role, change=change), self.assertRaises(ValueError):
                    findings.check_source(recorded, role)

    def test_crlf_checkout_accepted_without_changing_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'snapshot'
            shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
            for path in (snapshot / 'source').rglob('*'):
                if path.is_file():
                    path.write_bytes(path.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
            manifest = snapshot / 'manifest.json'
            manifest.write_bytes(manifest.read_bytes().replace(b'\n', b'\r\n'))
            with patch.object(findings, 'SOURCE_SNAPSHOT', snapshot):
                findings.check_source(self.full['source_sha256'], 'host')
                findings.check_source(self.full['trials'][0]['source_sha256'], 'worker')

    def test_changed_worker_fingerprint_and_measurement_rejected(self):
        for change in ('fingerprint', 'counter'):
            result = copy.deepcopy(self.full)
            if change == 'fingerprint':
                result['trials'][1]['source_sha256']['Dockerfile'] = '0' * 64
            else:
                result['trials'][0]['lookup_counters']['delta']['Innodb_data_read'] += 1
            with self.subTest(change=change), self.assertRaises(ValueError):
                findings.validate(result, findings.FULL, 'full')

    def test_invalid_source_rejected_before_outputs_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = root / 'snapshot'
            shutil.copytree(findings.SOURCE_SNAPSHOT, snapshot)
            (snapshot / 'source/scripts/run_cache_pressure.py').write_text('tampered\n')
            output = root / 'output'
            with patch.object(findings, 'SOURCE_SNAPSHOT', snapshot), self.assertRaises(ValueError):
                findings.build(output)
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
