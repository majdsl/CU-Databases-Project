"""Host-only, isolated MyRocks compression experiment; no existing .env is used."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import rocksdb_compression as benchmark
from benchmarks.run import save_json

PROJECT = re.compile(r'cu-compression-[0-9a-f]{32}-[1-9][0-9]*\Z')
IMAGE_ID = re.compile(r'sha256:[0-9a-f]{64}\Z')
SOURCE_FILES = ('scripts/run_rocksdb_compression.py', 'benchmarks/rocksdb_compression.py',
                'benchmarks/core.py', 'benchmarks/run.py', 'Dockerfile', 'requirements.txt',
                'docker/mariadb/Dockerfile', 'docker/mariadb/rocksdb.cnf')


class Experiment:
    def __init__(self, mode, power):
        benchmark.settings(mode)
        if not power.strip():
            raise ValueError('Record actual power conditions')
        self.mode = mode
        self.token = uuid.uuid4().hex
        self.owner = secrets.token_hex(16)
        self.credentials = {'MARIADB_ROOT_PASSWORD': secrets.token_hex(24),
                            'MARIADB_PASSWORD': secrets.token_hex(24)}
        self.environment = dict(os.environ, **self.credentials,
                                DB_PASSWORD=self.credentials['MARIADB_PASSWORD'],
                                COMPRESSION_ADMIN_PASSWORD=self.credentials['MARIADB_ROOT_PASSWORD'])
        self.run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-rocksdb-compression-' + self.token[:8]
        self.directory = ROOT / 'results' / self.run_id
        self.commands = []
        self.images = {}
        self.current = None
        self.result = dict(format_version=1, experiment='isolated_rocksdb_compression_v1',
                           run_id=self.run_id, mode=mode, power_condition=power, status='running',
                           schedule=benchmark.schedule(mode), trials=[],
                           host_platform=platform.platform(), host_machine=platform.machine(),
                           host_python=sys.version)

    def redact(self, value):
        for secret in self.credentials.values():
            value = value.replace(secret, '[REDACTED_CREDENTIAL]')
        for path in (str(ROOT), str(Path.home())):
            for representation in (path, path.replace('\\', '\\\\')):
                value = value.replace(representation, '<LOCAL_PATH>')
        return value

    def call(self, argv, private=False, check=True):
        print('Docker step:', ' '.join(argv[:3]), flush=True)
        started = time.perf_counter()
        response = subprocess.run(argv, cwd=ROOT, env=self.environment, text=True,
                                  encoding='utf-8', errors='replace',
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=900 if argv[1:2] == ['build'] else 600)
        recorded_argv = [self.redact(arg) for arg in argv]
        if argv[1:3] == ['context', 'inspect']:
            recorded_argv[3] = '<CURRENT_CONTEXT>'
        self.commands.append(dict(number=len(self.commands) + 1, argv=recorded_argv,
            elapsed_seconds=time.perf_counter() - started, exit_code=response.returncode,
            stdout='[private output omitted]' if private else self.redact(response.stdout),
            stderr=self.redact(response.stderr)))
        if self.directory.exists():
            save_json(self.directory / 'commands.json', self.commands)
        if response.stderr and not private:
            print(self.redact(response.stderr), file=sys.stderr, flush=True)
        if response.returncode and response.stdout and not private:
            print(self.redact(response.stdout), file=sys.stderr, flush=True)
        if check and response.returncode:
            raise RuntimeError('Command failed: ' + ' '.join(argv[:3]) +
                               f' (exit {response.returncode}); inspect commands.json')
        return response.stdout.strip()

    def checkpoint(self):
        save_json(self.directory / 'results.json', self.result)

    def preflight(self):
        if platform.machine().lower() not in ('amd64', 'x86_64'):
            raise RuntimeError('Use a local Intel/AMD x64 host; emulated ARM timing is outside this protocol')
        raw = self.call(['docker', 'info', '--format',
            '{"os":"{{.OSType}}","architecture":"{{.Architecture}}","version":"{{.ServerVersion}}",'
            '"kernel":"{{.KernelVersion}}","cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}'])
        docker = json.loads(raw)
        if docker['os'] != 'linux' or docker['architecture'] not in ('amd64', 'x86_64'):
            raise RuntimeError('A local Linux amd64 Docker engine is required')
        context = self.call(['docker', 'context', 'show'], private=True)
        endpoint = json.loads(self.call(['docker', 'context', 'inspect', context, '--format',
                                        '{{json .Endpoints.docker.Host}}'], private=True))
        actual_endpoint = os.environ.get('DOCKER_HOST', endpoint)
        if not actual_endpoint.startswith(('unix://', 'npipe://')):
            raise RuntimeError('Remote/TCP Docker contexts are outside this local-machine protocol')
        if self.mode != 'smoke':
            busy = self.call(['docker', 'ps', '--filter', 'label=com.docker.compose.project=cu-engine-lab',
                              '--format', '{{.ID}}'])
            other = self.call(['docker', 'ps', '--filter',
                'name=^/cu-(pressure|writes|storage|recovery|compression|stock)-', '--format', '{{.ID}}'])
            if busy or other:
                raise RuntimeError('Stop the normal lab and other experiments before measuring; preserve their volumes')
        self.result['docker'] = docker
        self.result['docker_endpoint_kind'] = actual_endpoint.split(':', 1)[0]
        self.result['git_commit'] = self.call(['git', 'rev-parse', 'HEAD'], check=False)
        dirty = []
        for args in (['git', 'diff', '--quiet'], ['git', 'diff', '--cached', '--quiet']):
            self.call(args, check=False)
            code = self.commands[-1]['exit_code']
            if code not in (0, 1):
                raise RuntimeError('Cannot determine tracked Git state')
            dirty.append(code == 1)
        self.result['git_tracked_changes'] = any(dirty)
        self.result['source_sha256'] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                                        for name in SOURCE_FILES}

    def build_images(self):
        for role, context in [('db', 'docker/mariadb'), ('runner', '.')]:
            tag = 'cu-compression-' + self.token + '-' + role + ':local'
            self.call(['docker', 'build', '--tag', tag, context])
            metadata = json.loads(self.call(['docker', 'image', 'inspect', tag, '--format',
                '{"id":"{{.Id}}","os":"{{.Os}}","architecture":"{{.Architecture}}"}']))
            if not IMAGE_ID.fullmatch(metadata['id']) or metadata['os'] != 'linux' or metadata['architecture'] != 'amd64':
                raise RuntimeError('Unexpected built image identity/platform')
            self.images[role] = metadata
        self.result['images'] = self.images
        self.checkpoint()

    def verify_worker_source(self, trial):
        recorded = trial.get('source_sha256', {})
        for path, digest in self.result['source_sha256'].items():
            if path != 'scripts/run_rocksdb_compression.py' and recorded.get(path) != digest:
                raise RuntimeError('Worker source differs from host fingerprint: ' + path)

    def run(self):
        self.directory.mkdir(parents=True, exist_ok=False)
        try:
            self.preflight()
            self.checkpoint()
            self.result['expected_data'] = {p: benchmark.oracle(p, benchmark.settings(self.mode)['rows'])
                                            for p in benchmark.PROFILES}
            self.checkpoint()
            self.build_images()
            for number, identity in enumerate(self.result['schedule'], 1):
                resources = TrialResources(self, number)
                resources.ensure_new()
                self.current = resources
                self.result['active_trial'] = dict(identity, project=resources.project)
                self.checkpoint()
                print('Compression trial:', identity, flush=True)
                resources.start_database(identity['codec'])
                raw = resources.run_worker(identity)
                (self.directory / f'trial-{number:02d}.json').write_text(raw + '\n', encoding='utf-8')
                trial = json.loads(raw)
                benchmark.validate_trial(trial, self.mode, identity, self.result['expected_data'][identity['profile']])
                self.verify_worker_source(trial)
                trial.update(position=identity['position'], project=resources.project, images=self.images)
                self.result['trials'].append(trial)
                self.checkpoint()
                trial['clean_stop'] = resources.stop_cleanly()
                self.checkpoint()
                inventory_raw = resources.read_inventory()
                (self.directory / f'trial-{number:02d}-inventory.json').write_text(inventory_raw + '\n', encoding='utf-8')
                trial['sst_inventory'] = json.loads(inventory_raw)
                trial['table_sst'] = benchmark.match_inventory(trial['sst_after_reads'], trial['sst_inventory'])
                self.checkpoint()
                trial['resource_cleanup'] = resources.cleanup()
                self.current = None
                self.result.pop('active_trial')
                self.checkpoint()
            self.result['status'] = 'completed'
            self.result['statistics'] = benchmark.summary(self.result)
            report = benchmark.markdown(self.result)
            (self.directory / 'summary.md').write_text(report, encoding='utf-8')
            self.result['commands_sha256'] = hashlib.sha256((self.directory / 'commands.json').read_bytes()).hexdigest()
            self.checkpoint()
            if self.mode == 'smoke':
                print('COMPRESSION_VALIDATION_JSON_BEGIN')
                print(json.dumps(self.result, indent=2, default=str))
                print('COMPRESSION_VALIDATION_JSON_END')
            print(report)
            print('Saved:', self.directory)
            return self.result
        except BaseException as error:
            self.result['status'] = 'failed'
            self.result['error_type'] = type(error).__name__
            self.result['error'] = self.redact(str(error))
            if self.current is not None:
                self.result['retained_project'] = self.current.project
                self.result['failure_stop'] = self.current.retain_on_failure()
            (self.directory / 'summary.md').unlink(missing_ok=True)
            self.checkpoint()
            print('Partial results:', self.directory, file=sys.stderr)
            if self.current:
                print('Owned isolated resources retained:', self.current.project, file=sys.stderr)
            raise


class TrialResources:
    def __init__(self, experiment, number):
        self.experiment = experiment
        self.project = f'cu-compression-{experiment.token}-{number}'
        if not PROJECT.fullmatch(self.project):
            raise ValueError('Invalid isolated compression project')
        self.volume = self.project + '-data'
        self.containers = {}
        self.labels = {'cu.compression.project': self.project, 'cu.compression.owner': experiment.owner}

    def name(self, role):
        if role not in ('db', 'worker', 'inventory'):
            raise ValueError('Unknown resource role')
        return self.project + '-' + role

    def call(self, *args, **kwargs):
        return self.experiment.call(['docker', *args], **kwargs)

    def label_args(self):
        return [part for key, value in self.labels.items() for part in ('--label', key + '=' + value)]

    def ensure_new(self):
        for role in ('db', 'worker', 'inventory'):
            if self.call('container', 'ls', '-a', '--filter', 'name=^/' + self.name(role) + '$', '--format', '{{.ID}}'):
                raise RuntimeError('Pre-existing container; refusing reuse')
        if self.call('volume', 'ls', '--filter', 'name=^' + self.volume + '$', '--format', '{{.Name}}'):
            raise RuntimeError('Pre-existing volume; refusing reuse')

    def volume_identity(self):
        volume = json.loads(self.call('volume', 'inspect', self.volume, private=True))[0]
        if volume.get('Name') != self.volume or any((volume.get('Labels') or {}).get(k) != v for k, v in self.labels.items()):
            raise RuntimeError('Volume ownership mismatch; refusing modification')
        return volume

    def identity(self, role):
        container_id = self.containers[role]
        info = json.loads(self.call('container', 'inspect', container_id, private=True))[0]
        config = info['HostConfig']
        labels = info['Config'].get('Labels') or {}
        expected_image = self.experiment.images['db' if role == 'db' else 'runner']['id']
        network = 'container:' + self.containers['db'] if role == 'worker' else 'none'
        expected_memory = (2 * 1024**3) if role == 'db' else 512 * 1048576
        expected_cpus = 2000000000 if role == 'db' else 1000000000
        if (info['Id'] != container_id or info['Name'] != '/' + self.name(role) or
                any(labels.get(k) != v for k, v in self.labels.items()) or
                info['Image'] != expected_image or config.get('NetworkMode') != network or
                config.get('PortBindings') or config.get('Memory') != expected_memory or
                config.get('NanoCpus') != expected_cpus):
            raise RuntimeError('Container identity/network/resource mismatch; refusing modification')
        mounts = info['Mounts']
        if role == 'worker':
            if mounts or not config.get('ReadonlyRootfs'):
                raise RuntimeError('Unexpected worker mount or writable root')
        else:
            destination = '/var/lib/mysql' if role == 'db' else '/snapshot'
            if (len(mounts) != 1 or mounts[0].get('Type') != 'volume' or mounts[0].get('Name') != self.volume or
                    mounts[0].get('Destination') != destination or mounts[0].get('RW') != (role == 'db')):
                raise RuntimeError('Unexpected data volume mount')
        self.volume_identity()
        return info

    def create(self, role, arguments):
        container_id = self.call('container', 'create', '--name', self.name(role), *self.label_args(),
                                  '--cpus', '2' if role == 'db' else '1', '--memory',
                                  '2g' if role == 'db' else '512m', *arguments)
        if not re.fullmatch(r'[0-9a-f]{64}', container_id):
            raise RuntimeError('Unexpected Docker container ID')
        self.containers[role] = container_id
        self.identity(role)
        return container_id

    def start_database(self, codec):
        self.call('volume', 'create', *self.label_args(), self.volume)
        self.volume_identity()
        database = self.create('db', [
            '--network', 'none', '--mount', f'type=volume,src={self.volume},dst=/var/lib/mysql',
            '--env', 'MARIADB_ROOT_PASSWORD', '--env', 'MARIADB_PASSWORD',
            '--env', 'MARIADB_DATABASE=engine_lab', '--env', 'MARIADB_USER=benchmark',
            '--health-cmd', 'healthcheck.sh --connect --innodb_initialized',
            '--health-interval', '2s', '--health-timeout', '5s', '--health-start-period', '30s',
            '--health-retries', '60', self.experiment.images['db']['id'],
            '--sql-mode=STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION',
            '--query-cache-type=0', '--query-cache-size=0', '--skip-log-bin',
            '--rocksdb-block-cache-size=' + str(benchmark.BLOCK_CACHE_BYTES),
            '--rocksdb-flush-log-at-trx-commit=1', '--rocksdb-collect-sst-properties=ON',
            '--rocksdb-ignore-unknown-options=OFF',
            '--rocksdb-default-cf-options=' + benchmark.cf_configuration(codec)])
        self.call('start', database)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            info = self.identity('db')
            state = info['State']
            if state.get('Health', {}).get('Status') == 'healthy':
                return
            if state.get('Status') in ('exited', 'dead'):
                raise RuntimeError('Isolated database exited during initialization')
            time.sleep(1)
        raise RuntimeError('Database did not become healthy within 180 seconds')

    def run_worker(self, identity):
        self.identity('db')
        worker = self.create('worker', [
            '--read-only', '--network', 'container:' + self.containers['db'],
            '--env', 'DB_HOST=127.0.0.1', '--env', 'DB_NAME=engine_lab', '--env', 'DB_PASSWORD',
            '--env', 'COMPRESSION_ADMIN_PASSWORD', '--env', 'COMPRESSION_EXPERIMENT=isolated-v1',
            self.experiment.images['runner']['id'], 'python', '-m', 'benchmarks.rocksdb_compression',
            '--mode', self.experiment.mode, '--profile', identity['profile'],
            '--codec', identity['codec'], '--round', str(identity['round'])])
        raw = self.call('start', '--attach', worker)
        state = self.identity('worker')['State']
        if state.get('Status') != 'exited' or state.get('ExitCode') != 0 or state.get('OOMKilled'):
            raise RuntimeError('Worker failed or was OOM-killed')
        return raw

    def stop_cleanly(self):
        self.identity('db')
        self.call('stop', '--timeout', '120', self.containers['db'])
        state = self.identity('db')['State']
        if state.get('Status') != 'exited' or state.get('ExitCode') != 0 or state.get('OOMKilled'):
            raise RuntimeError('Unclean shutdown; retain the volume')
        return {k: state.get(k) for k in ('Status', 'ExitCode', 'OOMKilled', 'FinishedAt')}

    def read_inventory(self):
        state = self.identity('db')['State']
        if state.get('Status') != 'exited' or state.get('ExitCode') != 0 or state.get('OOMKilled'):
            raise RuntimeError('Refusing a snapshot of a live or unclean database')
        helper = self.create('inventory', [
            '--read-only', '--user', '0:0', '--network', 'none',
            '--mount', f'type=volume,src={self.volume},dst=/snapshot,readonly',
            self.experiment.images['runner']['id'], 'python', '-m', 'benchmarks.rocksdb_compression', '--inventory'])
        raw = self.call('start', '--attach', helper)
        state = self.identity('inventory')['State']
        if state.get('Status') != 'exited' or state.get('ExitCode') != 0 or state.get('OOMKilled'):
            raise RuntimeError('Read-only inventory helper failed')
        return raw

    def cleanup(self):
        result = {}
        for role in ('inventory', 'worker', 'db'):
            state = self.identity(role)['State']
            if state.get('Status') != 'exited' or state.get('ExitCode') != 0 or state.get('OOMKilled'):
                raise RuntimeError('Refusing cleanup without successful stopped containers')
            self.call('rm', self.containers[role])
            result[role + '_removed'] = True
        self.volume_identity()
        self.call('volume', 'rm', self.volume)
        result['volume_removed'] = True
        return result

    def retain_on_failure(self):
        outcomes = {}
        for role in ('inventory', 'worker', 'db'):
            if role not in self.containers:
                continue
            try:
                info = self.identity(role)
                logs = self.call('logs', '--tail', '100', self.containers[role], check=False)
                if logs:
                    print(self.experiment.redact(logs), file=sys.stderr, flush=True)
                (self.experiment.directory / ('failure-' + role + '.log')).write_text(self.experiment.redact(logs) + '\n', encoding='utf-8')
                if info['State'].get('Status') == 'running':
                    self.call('stop', '--timeout', '120', self.containers[role])
                outcomes[role] = 'owned container stopped/preserved; volume retained'
            except BaseException:
                outcomes[role] = 'identity/stop check failed; inspect without deleting data'
        return outcomes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ('smoke', 'pilot', 'full'):
        mode.add_argument('--' + name, action='store_true')
    parser.add_argument('--power-condition', required=True)
    args = parser.parse_args()
    selected = 'smoke' if args.smoke else 'pilot' if args.pilot else 'full'
    experiment = None
    try:
        experiment = Experiment(selected, args.power_condition)
        experiment.run()
    except (Exception, KeyboardInterrupt) as error:
        detail = experiment.redact(str(error)) if experiment else str(error)
        print('FAILED:', type(error).__name__, detail, '; inspect the saved partial results', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
