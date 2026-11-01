"""Paired uncached signed-snapshot builds on a disposable GitHub-hosted CI VM.

This is a reconstruction experiment, not a measurement launcher or default build.
Output contains public package inputs and allowlisted image records, never .env.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.build_manifest import image_metadata, package_inventory, probe_command


def output(*argv):
    return subprocess.check_output(argv, cwd=ROOT, text=True).strip()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def logged(directory, name, argv):
    print(name + ': ' + ' '.join(argv), flush=True)
    with (directory / (name + '.txt')).open('w') as stream:
        subprocess.run(argv, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)


def image_record(image):
    info = json.loads(output('docker', 'image', 'inspect', image))[0]
    selected, _ = image_metadata(info, image)
    config = info.get('Config') or {}
    # Exclude Env, labels, history and Docker's host-specific paths.
    selected['runtime_configuration'] = {key: config.get(key) for key in
        ('User', 'WorkingDir', 'Entrypoint', 'Cmd', 'ExposedPorts', 'Volumes', 'StopSignal')}
    return selected


def probe(image, command):
    return probe_command(image, ['/var/lib/mysql'], command[0], command[1:])


def preflight(directory):
    revision = output('git', 'rev-parse', 'HEAD')
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'):
        raise RuntimeError('This experiment only runs on a disposable GitHub-hosted runner')
    if revision != os.environ.get('GITHUB_SHA') or output('git', 'status', '--porcelain'):
        raise RuntimeError('The experiment requires the exact clean CI source revision')
    docker = json.loads(output('docker', 'info', '--format',
        '{"driver":{{json .Driver}},"root":{{json .DockerRootDir}},'
        '"memory_bytes":{{json .MemTotal}},"cpus":{{json .NCPU}}}'))
    disks = {key: dict(zip(('total', 'used', 'free'), shutil.disk_usage(path)))
             for key, path in (('checkout', ROOT), ('docker', Path(docker.pop('root'))))}
    record = dict(source_commit=revision, docker=docker, physical_filesystem_bytes=disks,
        classification='paired clean-build correctness experiment; no performance measurements',
        workflow_run_url=f"{os.environ['GITHUB_SERVER_URL']}/{os.environ['GITHUB_REPOSITORY']}"
                         f"/actions/runs/{os.environ['GITHUB_RUN_ID']}")
    write_json(directory / 'preflight.json', record)
    logged(directory, 'preflight-resources', ['docker', 'system', 'df'])
    if docker['driver'] == 'vfs' or any(d['free'] < 20 * 1024**3 for d in disks.values()):
        raise RuntimeError('Requires non-vfs Docker storage and at least 20 GiB physically free')
    if docker['memory_bytes'] < 4 * 1024**3 or docker['cpus'] < 2:
        raise RuntimeError('Requires at least 4 GiB Docker memory and two CPUs')
    return revision


def run(directory):
    revision = preflight(directory)
    suffix = os.environ['GITHUB_RUN_ID'] + '-' + os.environ['GITHUB_RUN_ATTEMPT']
    if not re.fullmatch(r'[0-9]+-[0-9]+', suffix):
        raise RuntimeError('Invalid CI resource identity')
    logged(directory, 'create-local-credentials', [sys.executable, 'scripts/init_env.py'])
    logged(directory, 'fetch-pinned-data', [sys.executable, 'scripts/fetch_openflights.py'])
    runner_tag = 'cu-reconstruction-runner:' + suffix
    logged(directory, 'runner-build', ['docker', 'build', '--pull', '--progress=plain',
        '--tag', runner_tag, '.'])
    runner_id = output('docker', 'image', 'inspect', '--format', '{{.Id}}', runner_tag)
    runner = image_record(runner_id)
    write_json(directory / 'runner-image.json', runner)
    logged(directory, 'runner-unit-tests', ['docker', 'run', '--rm', '--pull=never',
        '--network=none', '--entrypoint', 'python', runner_id,
        '-m', 'unittest', 'discover', '-s', 'tests', '-v'])
    builds = []
    for label in ('a', 'b'):
        case = directory / ('build-' + label)
        case.mkdir()
        tag = 'cu-reconstruction-db:' + suffix + '-' + label
        logged(case, 'uncached-build', ['docker', 'build', '--no-cache', '--pull',
            '--progress=plain', '--file', 'docker/reconstruction/Dockerfile',
            '--tag', tag, 'docker'])
        image_id = output('docker', 'image', 'inspect', '--format', '{{.Id}}', tag)
        image = image_record(image_id)
        packages = output(*probe(image_id, ['/usr/bin/dpkg-query', '-W',
            '-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n']))
        image['installed_packages'] = package_inventory(packages)
        (case / 'installed-packages.txt').write_text(packages + '\n')
        write_json(case / 'image.json', image)
        # Includes signed release files, exact indexes, downloaded additions and hashes.
        with (case / 'package-inputs.tar').open('wb') as stream:
            subprocess.run(probe(image_id, ['/bin/tar', '-C',
                '/usr/local/share/reconstruction', '-cf', '-', '.']), cwd=ROOT,
                stdout=stream, check=True)
        override = case / 'images.compose.json'
        write_json(override, dict(services=dict(db=dict(image=image_id), runner=dict(image=runner_id))))
        project = 'cu-reconstruction-' + suffix + '-' + label
        compose = ['docker', 'compose', '-p', project, '-f', 'compose.yaml', '-f', str(override)]
        try:
            logged(case, 'database-start', compose + ['up', '-d', '--no-build', '--pull',
                'never', '--wait', '--wait-timeout', '180', 'db'])
            # `compose run` has no --no-build flag. The selected image already exists;
            # no --build is requested, and --no-deps keeps the running DB untouched.
            logged(case, 'five-engine-readback', compose + ['run', '--rm', '--no-deps',
                '--pull', 'never', 'runner'])
            observed = output('docker', 'inspect', '--format', '{{.Image}}',
                              output(*compose, 'ps', '-q', 'db'))
            if observed != image_id:
                raise RuntimeError('Actual database container used a different image')
            image['actual_database_image'] = observed
            image['five_engine_readback'] = 'passed'
            builds.append(image)
        finally:
            # These uniquely named CI stacks are owned by this experiment. Retain volumes.
            logged(case, 'database-logs', compose + ['logs', '--no-color', '--tail', '200', 'db'])
            logged(case, 'database-stop', compose + ['stop', '-t', '120', 'db'])
            container = output(*compose, 'ps', '-a', '-q', 'db')
            if not container:
                raise RuntimeError('Expected the owned database container after shutdown')
            details = json.loads(output('docker', 'inspect', container))[0]
            labels = (details.get('Config') or {}).get('Labels') or {}
            state = details.get('State') or {}
            shutdown = dict(image_id=details.get('Image'),
                compose_project=labels.get('com.docker.compose.project'),
                compose_service=labels.get('com.docker.compose.service'),
                state={key: state.get(key) for key in ('Status', 'Running', 'ExitCode', 'OOMKilled')})
            write_json(case / 'shutdown.json', shutdown)
            if (shutdown['image_id'] != image_id or shutdown['compose_project'] != project or
                    shutdown['compose_service'] != 'db' or shutdown['state'] !=
                    dict(Status='exited', Running=False, ExitCode=0, OOMKilled=False)):
                raise RuntimeError('Owned database did not stop cleanly with the expected image')
    if output('git', 'rev-parse', 'HEAD') != revision or output('git', 'status', '--porcelain', '--untracked-files=no'):
        raise RuntimeError('Source changed during the reconstruction experiment')
    comparison = dict(source_commit=revision, runner_image=runner_id,
        builds=[dict(image_id=b['image_id'], five_engine_readback=b['five_engine_readback'],
                     actual_database_image=b['actual_database_image']) for b in builds],
        package_inventories_identical=builds[0]['installed_packages'] == builds[1]['installed_packages'],
        image_config_ids_identical=builds[0]['image_id'] == builds[1]['image_id'],
        rootfs_diff_ids_identical=builds[0]['rootfs_diff_ids'] == builds[1]['rootfs_diff_ids'],
        selected_runtime_configuration_identical=builds[0]['runtime_configuration'] == builds[1]['runtime_configuration'],
        scope='Two --no-cache --pull DB builds on one disposable daemon; base layers shared; '
              'one frozen runner image; no timed workloads; images not published to a registry')
    write_json(directory / 'comparison.json', comparison)
    print(json.dumps(comparison, indent=2), flush=True)
    print('PAIRED BUILD CORRECTNESS PASS; inspect identity comparisons before making byte-equality claims.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    directory = args.output.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    try:
        run(directory)
    finally:
        (directory / '.gitattributes').write_text('* -text\n')
        inputs = [Path('scripts/check_build_reconstruction.py'), Path('scripts/build_manifest.py'),
                  Path('report-tests/test_build_reconstruction.py'),
                  Path('.github/workflows/build-reconstruction.yml'), Path('.dockerignore'),
                  Path('Dockerfile'), Path('requirements.txt'), Path('compose.yaml'),
                  Path('docker/mariadb/rocksdb.cnf'),
                  *(p.relative_to(ROOT) for p in sorted((ROOT / 'docker/reconstruction').glob('*')))]
        write_json(directory / 'source-inputs.json', {p.as_posix(): hashlib.sha256((ROOT / p).read_bytes()).hexdigest()
                   for p in inputs if (ROOT / p).is_file()})
        paths = sorted(p for p in directory.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.txt')
        (directory / 'SHA256SUMS.txt').write_text(''.join(
            hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.relative_to(directory).as_posix() + '\n'
            for p in paths))


if __name__ == '__main__':
    main()
