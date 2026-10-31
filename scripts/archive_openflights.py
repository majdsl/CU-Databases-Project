"""Export a completed, cleanly stopped OpenFlights pilot/full session as evidence.

The export reads fixed evidence files only, verifies the launcher's recorded hashes
and benchmark statistics, and never calls Docker or modifies the original results.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import run_openflights as launcher

SHA256 = re.compile(r'[0-9a-f]{64}\Z')
MAX_FILE_BYTES = 32 * 1024 * 1024

# The verifier deliberately has no project imports and does not extract ZIP data.
VERIFIER = r'''"""Verify every file and checksum in an OpenFlights evidence export."""
import hashlib
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile


def safe(name):
    p = PurePosixPath(name)
    return bool(name) and not p.is_absolute() and '..' not in p.parts and '\\' not in name and ':' not in name and str(p) == name


def verify(target):
    if target.is_file():
        with zipfile.ZipFile(target) as z:
            names = z.namelist()
            if len(names) != len(set(names)) or any(not safe(n) for n in names):
                raise ValueError('Unsafe or duplicate ZIP entries')
            if any(stat.S_ISLNK(info.external_attr >> 16) for info in z.infolist()):
                raise ValueError('Symlink ZIP entry')
            data = {name: z.read(name) for name in names}
    else:
        data = {}
        for path in target.rglob('*'):
            if path.is_symlink():
                raise ValueError('Symlink in extracted bundle')
            if path.is_file():
                name = path.relative_to(target).as_posix()
                if not safe(name):
                    raise ValueError('Unsafe bundle path')
                data[name] = path.read_bytes()
    entries = {}
    for line in data['SHA256SUMS.txt'].decode('utf-8').splitlines():
        digest, name = line.split('  ', 1)
        if not re.fullmatch('[0-9a-f]{64}', digest) or not safe(name) or name in entries:
            raise ValueError('Invalid checksum entry')
        entries[name] = digest
    if not entries or set(entries) != set(data) - {'SHA256SUMS.txt'}:
        raise ValueError('Checksum coverage differs from bundle contents')
    for name, digest in entries.items():
        if hashlib.sha256(data[name]).hexdigest() != digest:
            raise ValueError('Checksum mismatch: ' + name)
    print('BUNDLE CHECKSUMS PASS: ' + str(len(entries)) + ' files; integrity only, not authenticity or SQL re-execution.')


if __name__ == '__main__':
    try:
        if len(sys.argv) > 2:
            raise ValueError('Usage: python verify.py [archive.zip or extracted-directory]')
        verify(Path(sys.argv[1]).absolute() if len(sys.argv) == 2 else Path(__file__).resolve().parent)
    except Exception as error:
        print('FAILED: ' + str(error), file=sys.stderr)
        sys.exit(1)
'''


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_regular(path, root):
    """Read a contained regular file without following symlinks or hard links."""
    root = Path(root).absolute()
    path = Path(path).absolute()
    try:
        relative = path.relative_to(root)
    except ValueError as error:
        raise ValueError('Evidence path is outside the results directory') from error
    require('..' not in relative.parts, 'Parent traversal is not an evidence path')
    current = root
    require(not current.is_symlink(), 'Results directory must not be a symlink')
    for part in relative.parts:
        current = current / part
        require(not current.is_symlink(), 'Evidence paths must not contain symlinks')
    info = path.stat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'Evidence must be a regular file with one filesystem link')
    require(info.st_size <= MAX_FILE_BYTES, 'Evidence file is unexpectedly large')
    return path.read_bytes()


def validate_result(session, mode, reference, raw, summary):
    result = json.loads(raw)
    require(result.get('format_version') == 1 and result.get('experiment') == 'openflights_routes_v1',
            'Unsupported raw OpenFlights evidence')
    require(result.get('run_id') == reference['run_id'], 'Raw run identity differs')
    require(result.get('config') == vars(launcher.benchmark.Config(pilot=mode == 'pilot')),
            'Raw run does not have the expected pilot/full configuration')
    for field in ('source_sha256', 'dataset_sha256', 'rows', 'power_condition'):
        require(result.get(field) == session.get(field), 'Raw evidence differs from session: ' + field)
    for field in ('runtime', 'server_version', 'global_variables', 'session_variables'):
        require(result.get(field) == session['control_reference'].get(field),
                'Raw evidence differs from recorded controls: ' + field)
    require(launcher.benchmark.summarize(result) == result.get('statistics'),
            'Raw statistics differ from the verified trials')
    require(launcher.benchmark.markdown(result) == summary.decode('utf-8').replace('\r\n', '\n').replace('\r', '\n'),
            'Raw summary differs from its recorded trials')
    return result


def collect(session_path):
    results_root = launcher.ROOT / 'results'
    # Check the caller's lexical path before launcher.load_session resolves it.
    session_path = Path(session_path).absolute()
    source_session = read_regular(session_path, results_root)
    require(not (session_path.parent / '.operation.lock').exists(),
            'A session operation is active; finish it before exporting')
    # Do not let the launcher's parser follow evidence symlinks before our own
    # fixed-file collector gets a chance to reject them.
    read_regular(session_path.parent / 'runtime-images.compose.json', results_root)
    read_regular(session_path.parent / 'build-images.compose.json', results_root)
    initial = json.loads(source_session)
    if initial.get('build_manifest') is not None:
        require(initial['build_manifest'].get('file') == 'build-manifest.json', 'Unexpected build manifest path')
        read_regular(session_path.parent / 'build-manifest.json', results_root)
    session, path = launcher.load_session(session_path)
    require(source_session == path.read_bytes(), 'Session changed while loading')
    require(session.get('status') == 'completed' and session.get('pilot_review_acknowledged') is True,
            'Export requires a completed reviewed pilot and full session')
    database = session.get('database', {})
    stop = session.get('database_stop', {})
    stop_state = stop.get('state', {})
    require(stop_state.get('Status') == 'exited' and stop_state.get('ExitCode') == 0
            and stop_state.get('OOMKilled') is False,
            'Export requires the session database to have a recorded clean stop')
    require(bool(database.get('container_id')) and stop.get('container_id') == database.get('container_id')
            and stop.get('image_id') == session['images']['db']
            and stop.get('selected_reference') == session['images']['db']
            and stop_state.get('StartedAt') == database.get('state', {}).get('StartedAt'),
            'Stopped database identity differs from the measured session')

    files = {}
    originals = {}

    def add(source, expected=None):
        data = read_regular(source, results_root)
        if expected is not None:
            require(isinstance(expected, str) and SHA256.fullmatch(expected) is not None,
                    'Invalid recorded evidence checksum')
            require(hashlib.sha256(data).hexdigest() == expected, 'Recorded evidence checksum differs')
        key = source.relative_to(launcher.ROOT).as_posix()
        require(key not in files, 'Repeated evidence path')
        files[key] = data
        originals[source] = data
        return data

    add(path)
    require(files[path.relative_to(launcher.ROOT).as_posix()] == source_session, 'Session changed during collection')
    add(path.parent / 'runtime-images.compose.json')
    add(path.parent / 'build-images.compose.json')
    manifest = session.get('build_manifest')
    if manifest is not None:
        require(manifest.get('file') == 'build-manifest.json', 'Unexpected build manifest path')
        add(path.parent / 'build-manifest.json', manifest['sha256'])

    runs = {}
    for mode in ('pilot', 'full'):
        stage = session.get('stages', {}).get(mode, {})
        require(stage.get('status') == 'completed', 'Both pilot and full stages must be completed')
        require(stage.get('controls') == {'before': session['control_reference'], 'after': session['control_reference']},
                'Recorded stage controls differ from the session')
        stage_db = stage.get('database_after', {})
        require(stage_db.get('container_id') == database['container_id']
                and stage_db.get('image_id') == session['images']['db']
                and stage_db.get('state', {}).get('StartedAt') == stop_state.get('StartedAt'),
                'Stage database differs from the cleanly stopped database')
        worker_before = stage.get('runner_before', {})
        worker_after = stage.get('runner_after', {})
        worker_state = worker_after.get('state', {})
        require(bool(worker_before.get('container_id'))
                and worker_after.get('container_id') == worker_before.get('container_id')
                and all(item.get('image_id') == session['images']['runner']
                        and item.get('selected_reference') == session['images']['runner']
                        for item in (worker_before, worker_after))
                and worker_state.get('Status') == 'exited' and worker_state.get('ExitCode') == 0
                and worker_state.get('OOMKilled') is False,
                'Stage worker did not record successful execution of the selected image')
        reference = stage.get('result', {})
        run_id = reference.get('run_id', '')
        require(isinstance(run_id, str) and launcher.RUN_ID.fullmatch(run_id) is not None,
                'Invalid pilot/full run identity')
        require(run_id not in runs.values(), 'Pilot and full must have different run identities')
        directory = results_root / run_id
        raw = add(directory / 'results.json', reference.get('results_sha256'))
        summary = add(directory / 'summary.md', reference.get('summary_sha256'))
        validate_result(session, mode, reference, raw, summary)
        add(path.parent / (mode + '-transcript.txt'))
        add(path.parent / (mode + '-command.compose.json'))
        runs[mode] = run_id

    # Refuse concurrent edits, preserving the exact validated byte snapshots.
    require(not (path.parent / '.operation.lock').exists(), 'Session operation started during export')
    for source, data in originals.items():
        require(read_regular(source, results_root) == data, 'Evidence changed during export')
    files['README.md'] = (
        '# OpenFlights evidence export\n\n'
        'Tested source commit: ' + str(session.get('host', {}).get('commit', 'unavailable')) + '\n\n'
        'Pilot: ' + runs['pilot'] + '\nFull: ' + runs['full'] + '\n\n'
        'The original results/ paths are preserved. Pilot observations and full-run statistics remain separate. '
        'The session records immutable selected images, source/dataset hashes, controls, commands and a clean database stop. '
        'A build manifest is included when the producing launcher recorded one. Existing source/results/database volumes were not changed.\n\n'
        'Extract to a new directory and run `python verify.py` (use `python3` on Linux). '
        'The extracted verifier can also check the ZIP directly: `python verify.py path/to/openflights-evidence.zip`. '
        'Checksums detect changed or missing bytes; they are not signatures, independent observation or SQL re-execution.\n\n'
        'This export includes only known evidence filenames. It excludes .env, credentials files, '
        'external build-adapter contents and unrelated results. Review any privately customized output before sharing. '
        'The bundle is a new copy of this session, not recovery of another chat or historical ZIP. '
        'Backing up or publishing this file is a separate action; results/ is ignored by Git.\n'
    ).encode('utf-8')
    files['verify.py'] = VERIFIER.encode('utf-8')
    files['SHA256SUMS.txt'] = ''.join(hashlib.sha256(data).hexdigest() + '  ' + name + '\n'
                                    for name, data in sorted(files.items())).encode('utf-8')
    return files


def export(session_path, output):
    output = Path(output).absolute()
    require(output.suffix.lower() == '.zip', 'Choose an output filename ending in .zip')
    require(not output.exists() and not output.is_symlink(), 'Output already exists; choose a new filename')
    require(output.parent.is_dir(), 'Output parent directory must already exist')
    current = output.parent
    while current != current.parent:
        require(not current.is_symlink(), 'Output parent must not contain symlinks')
        current = current.parent
    files = collect(session_path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.' + output.name + '.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
        with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                archive.writestr(name, data)
        # Same-directory hard link publishes complete bytes without overwriting
        # any path another process created during validation or compression.
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    print('Saved evidence ZIP:', output)
    print('Original results and database volumes retained. Copy the ZIP outside this workspace for backup.')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True, type=Path, help='Completed and stopped results/.../session.json')
    parser.add_argument('--output', required=True, type=Path, help='New .zip path; existing files are never overwritten')
    args = parser.parse_args()
    try:
        export(args.session, args.output)
    except (Exception, KeyboardInterrupt) as error:
        print('FAILED:', str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
