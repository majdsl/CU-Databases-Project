"""Portable evidence export: verified full/pilot inputs, no secrets or overwrite."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import archive_openflights as archive
from scripts import run_openflights as host

SOURCE = Path(__file__).resolve().parents[1]
PILOT = '20261030T184911Z-openflights-329f0869'
FULL = '20261030T184936Z-openflights-85032cd6'


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='evidence export ')
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.root = self.directory / 'repo with spaces'
        self.session_dir = self.root / 'results' / 'session with spaces'
        self.session_dir.mkdir(parents=True)
        self.path = self.session_dir / 'session.json'
        self.output = self.directory / 'evidence with spaces.zip'
        self.patcher = patch.object(host, 'ROOT', self.root)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        raw = json.loads((SOURCE / 'evidence/openflights' / FULL / 'results.json').read_text())
        controls = {k: raw[k] for k in ('source_sha256', 'dataset_sha256', 'rows', 'runtime',
                                       'server_version', 'global_variables', 'session_variables')}
        images = {'db': 'sha256:' + 'b' * 64, 'runner': 'sha256:' + 'c' * 64}
        database = dict(container_id='db-owned', image_id=images['db'], selected_reference=images['db'],
                        state=dict(Status='running', ExitCode=0, OOMKilled=False, StartedAt='same-start'))
        stop = copy.deepcopy(database)
        stop['state']['Status'] = 'exited'
        self.session = dict(format_version=1, experiment='immutable_openflights_v1', token='a' * 32,
                            project='cu-openflights-' + 'a' * 32, images=images, status='completed',
                            stages={}, host={'commit': '5afc5f03f697c3ad1ed92feafade0d49e3261cd0'},
                            commands=[], source_sha256=raw['source_sha256'], rows=raw['rows'],
                            dataset_sha256=raw['dataset_sha256'], power_condition=raw['power_condition'],
                            control_reference=controls, pilot_review_acknowledged=True,
                            database=database, database_stop=stop)
        for mode, run_id in [('pilot', PILOT), ('full', FULL)]:
            result = json.loads((SOURCE / 'evidence/openflights' / run_id / 'results.json').read_text())
            dest = self.root / 'results' / run_id
            dest.mkdir()
            # Keep real archived trials while using a matching fixture's controls.
            for key in ('runtime', 'server_version', 'global_variables', 'session_variables',
                        'source_sha256', 'power_condition'):
                result[key] = raw[key]
            raw_bytes = (json.dumps(result, indent=2) + '\n').encode()
            summary = host.benchmark.markdown(result).encode()
            (dest / 'results.json').write_bytes(raw_bytes)
            (dest / 'summary.md').write_bytes(summary)
            worker = dict(container_id='runner-' + mode, image_id=images['runner'], selected_reference=images['runner'],
                          state=dict(Status='exited', ExitCode=0, OOMKilled=False))
            self.session['stages'][mode] = dict(status='completed', database_after=copy.deepcopy(database),
                runner_before=copy.deepcopy(worker), runner_after=copy.deepcopy(worker),
                controls={'before': controls, 'after': controls},
                result={'run_id': run_id, 'results_sha256': hashlib.sha256(raw_bytes).hexdigest(),
                        'summary_sha256': hashlib.sha256(summary).hexdigest()})
            (self.session_dir / (mode + '-transcript.txt')).write_text('Successful fixture output\n')
            (self.session_dir / (mode + '-command.compose.json')).write_text('{"services": {}}\n')
        host.save_json(self.session_dir / 'runtime-images.compose.json', host.expected_runtime(self.session))
        host.save_json(self.session_dir / 'build-images.compose.json', {'services': {}})
        (self.root / '.env').write_text('DB_PASSWORD=never-export-this-secret\n')
        (self.session_dir / '.env').write_text('another-private-marker\n')
        (self.session_dir / 'unrelated.txt').write_text('unrelated-private-marker\n')
        self.save()

    def save(self):
        host.save_json(self.path, self.session)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def test_export_preserves_inputs_excludes_private_files_and_keeps_runs_separate(self):
        before = self.snapshot()
        archive.export(self.path, self.output)
        self.assertEqual(before, self.snapshot())
        with zipfile.ZipFile(self.output) as zipped:
            names = zipped.namelist()
            self.assertIn('results/' + PILOT + '/results.json', names)
            self.assertIn('results/' + FULL + '/results.json', names)
            self.assertNotIn('.env', ' '.join(names))
            self.assertNotIn('unrelated.txt', ' '.join(names))
            content = b''.join(zipped.read(name) for name in names)
            self.assertNotIn(b'never-export-this-secret', content)
            self.assertNotIn(b'another-private-marker', content)
            self.assertNotIn(b'unrelated-private-marker', content)
            self.assertEqual(json.loads(zipped.read('results/' + PILOT + '/results.json'))['config']['pilot'], True)
            self.assertEqual(json.loads(zipped.read('results/' + FULL + '/results.json'))['config']['pilot'], False)
            unpacked = self.directory / 'unpacked'
            zipped.extractall(unpacked)
        verified = subprocess.run([sys.executable, str(unpacked / 'verify.py')], capture_output=True, text=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn('BUNDLE CHECKSUMS PASS', verified.stdout)
        verified = subprocess.run([sys.executable, str(unpacked / 'verify.py'), str(self.output)], capture_output=True, text=True)
        self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_missing_tampered_or_incomplete_evidence_leaves_no_archive(self):
        raw_path = self.root / 'results' / FULL / 'results.json'
        original = raw_path.read_bytes()
        for mutation in ('missing', 'hash', 'trials', 'failed', 'wrong-mode'):
            with self.subTest(mutation=mutation):
                raw_path.write_bytes(original)
                result = json.loads(original)
                if mutation == 'missing':
                    raw_path.unlink()
                elif mutation == 'hash':
                    raw_path.write_bytes(original + b' ')
                else:
                    if mutation == 'trials': result['trials'].pop()
                    elif mutation == 'failed': result['status'] = 'failed'
                    else: result['config']['pilot'] = True
                    raw_path.write_text(json.dumps(result))
                    self.session['stages']['full']['result']['results_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                    self.save()
                with self.assertRaises((ValueError, FileNotFoundError)):
                    archive.export(self.path, self.output)
                self.assertFalse(self.output.exists())
                self.assertFalse(list(self.directory.glob('.*.tmp')))
        raw_path.write_bytes(original)

    def test_clean_stop_review_and_stage_controls_are_required(self):
        original = copy.deepcopy(self.session)
        for mutation in ('not-stopped', 'oom', 'foreign-db', 'unreviewed', 'stage-failed', 'worker-failed', 'controls'):
            with self.subTest(mutation=mutation):
                self.session = copy.deepcopy(original)
                if mutation == 'not-stopped': self.session.pop('database_stop')
                elif mutation == 'oom': self.session['database_stop']['state']['OOMKilled'] = True
                elif mutation == 'foreign-db': self.session['database_stop']['container_id'] = 'foreign'
                elif mutation == 'unreviewed': self.session['pilot_review_acknowledged'] = False
                elif mutation == 'stage-failed': self.session['stages']['full']['status'] = 'failed'
                elif mutation == 'worker-failed': self.session['stages']['full']['runner_after']['state']['ExitCode'] = 1
                else: self.session['stages']['pilot']['controls'] = {}
                self.save()
                with self.assertRaises(ValueError): archive.export(self.path, self.output)
                self.assertFalse(self.output.exists())

    def test_symlinked_inputs_and_run_path_traversal_are_refused(self):
        raw = self.root / 'results' / FULL / 'results.json'
        saved = raw.read_bytes()
        outside = self.directory / 'outside.json'
        outside.write_bytes(saved)
        raw.unlink()
        raw.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            archive.export(self.path, self.output)
        raw.unlink()
        raw.write_bytes(saved)
        self.session['stages']['full']['result']['run_id'] = '../outside'
        self.save()
        with self.assertRaisesRegex(ValueError, 'run identity'):
            archive.export(self.path, self.output)
        self.assertFalse(self.output.exists())

    def test_existing_output_and_publication_race_never_overwrite(self):
        self.output.write_bytes(b'keep existing backup')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            archive.export(self.path, self.output)
        self.assertEqual(self.output.read_bytes(), b'keep existing backup')
        self.output.unlink()
        original_link = archive.os.link
        def race(source, destination):
            Path(destination).write_bytes(b'another process created this')
            return original_link(source, destination)
        with patch.object(archive.os, 'link', side_effect=race), self.assertRaises(FileExistsError):
            archive.export(self.path, self.output)
        self.assertEqual(self.output.read_bytes(), b'another process created this')
        self.assertFalse(list(self.directory.glob('.*.tmp')))

    def test_offline_verifier_rejects_corruption_and_unlisted_files(self):
        archive.export(self.path, self.output)
        with zipfile.ZipFile(self.output) as zipped:
            contents = {name: zipped.read(name) for name in zipped.namelist()}
        verify = self.directory / 'verify.py'
        verify.write_bytes(contents['verify.py'])
        for mutation in ('changed', 'extra', 'traversal'):
            with self.subTest(mutation=mutation):
                altered = dict(contents)
                if mutation == 'changed': altered['results/' + FULL + '/results.json'] += b'changed'
                elif mutation == 'extra': altered['unlisted.txt'] = b'not covered'
                else: altered['../unsafe'] = b'bad path'
                corrupt = self.directory / (mutation + '.zip')
                with zipfile.ZipFile(corrupt, 'w') as zipped:
                    for name, data in altered.items(): zipped.writestr(name, data)
                result = subprocess.run([sys.executable, str(verify), str(corrupt)], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0)

    def test_version_two_build_manifest_is_included_and_cannot_change(self):
        self.session['format_version'] = 2
        self.session['host']['build_manifest_helper_sha256'] = 'd' * 64
        manifest = dict(format_version=1, collector_sha256='d' * 64,
                        source_commit=self.session['host']['commit'],
                        source_sha256=self.session['source_sha256'],
                        images={role: {'image_id': image} for role, image in self.session['images'].items()})
        data = (json.dumps(manifest) + '\n').encode()
        path = self.session_dir / 'build-manifest.json'
        path.write_bytes(data)
        self.session['build_manifest'] = {'file': 'build-manifest.json', 'sha256': hashlib.sha256(data).hexdigest()}
        self.save()
        archive.export(self.path, self.output)
        with zipfile.ZipFile(self.output) as zipped:
            self.assertEqual(zipped.read('results/session with spaces/build-manifest.json'), data)
        self.output.unlink()
        path.write_bytes(data + b'changed')
        with self.assertRaisesRegex(RuntimeError, 'checksum differs'):
            archive.export(self.path, self.output)
        self.assertFalse(self.output.exists())

    def test_windows_summary_bytes_are_retained_after_universal_newline_validation(self):
        for mode in ('pilot', 'full'):
            reference = self.session['stages'][mode]['result']
            path = self.root / 'results' / reference['run_id'] / 'summary.md'
            path.write_bytes(path.read_bytes().replace(b'\n', b'\r\n'))
            reference['summary_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save()
        archive.export(self.path, self.output)
        with zipfile.ZipFile(self.output) as zipped:
            self.assertIn(b'\r\n', zipped.read('results/' + FULL + '/summary.md'))


if __name__ == '__main__':
    unittest.main()
