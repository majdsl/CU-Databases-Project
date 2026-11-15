"""Run the four-engine tutorial on a fresh, disposable official MariaDB image."""
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
import threading
import time

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.tutorial_checks import COMMON_FILES, TutorialChecks, require

ROOT = Path(__file__).resolve().parents[1]
IMAGE = 'mariadb@sha256:8b5f33ebd85d1775657e974ed10434128bb493c80e826ceaa54074fd1a92a112'
PROJECT = re.compile(r'cu-stock-(?:[0-9a-f]{12}|[0-9]+-[0-9]+-(?:amd64|arm64))\Z')
PROJECT_LABEL = 'cu.tutorial.project'
OWNER_LABEL = 'cu.tutorial.owner'
CLIENT = ('export MYSQL_PWD="$MARIADB_PASSWORD"; exec mariadb --abort-source-on-error '
          '--batch --raw --skip-column-names -ututorial engine_lab')
ENGINE_NAMES = dict(innodb='InnoDB', aria='Aria', myisam='MyISAM', memory='MEMORY')
NEXT_STEPS = {
    'Docker check': 'Start Docker with Linux containers (amd64 or ARM64), then check that docker info works.',
    'resource check': 'If you supplied --project, retry without it to use a fresh name.',
    'image download': 'Check access to Docker Hub and free space in Docker, then retry.',
    'server startup': 'Check Docker memory, disk space and access to this checkout.',
    'SQL checks': 'Open validation.json and inspect the failed commands in transcript.txt.',
    'server restart': 'Check Docker is still running and inspect the server diagnostics in transcript.txt.',
    'cleanup': 'Keep the saved diagnostics and see docs/stock-tutorial-validation.md for troubleshooting.',
}


def validate_project(project):
    if not PROJECT.fullmatch(project):
        raise ValueError('Use an automatically generated project or cu-stock-<run>-<attempt>-<amd64|arm64>')


def architecture(value):
    aliases = {'amd64': 'amd64', 'x86_64': 'amd64', 'arm64': 'arm64', 'aarch64': 'arm64'}
    if value.lower() not in aliases:
        raise ValueError('Stock tutorial currently supports Linux amd64 and arm64 Docker engines')
    return aliases[value.lower()]


def render_summary(evidence):
    sequence = evidence['sequences'][0]
    access = {'ref': 'Indexed lookup', 'range': 'Index range', 'ALL': 'Full table scan'}
    lines = [
        '# Stock MariaDB tutorial: passed', '',
        f"MariaDB {evidence['server_version']} on a Linux {evidence['architecture']} Docker engine. "
        'These are correctness results.', '',
        '## MEMORY indexes', '',
        '| Filter | Index | Matching rows | Access path |',
        '| --- | --- | ---: | --- |',
    ]
    for item in sequence['indexes']:
        plan = item['access']
        lines.append(f"| `{item['predicate']}` | {item['index'].upper()} | {item['count']} | "
                     f"{access[plan]} (`{plan}`) |")
    lines += [
        '', 'Both indexes can look up an exact key. BTREE can also seek into an ordered range; '
        'HASH scanned the whole table for this range.', '',
        '## Rollback and restart', '',
        'In the transfer example, only InnoDB restored the original balances after rollback.', '',
        '| Engine | Rollback undid the transfer | Rows after restart (separate test) |',
        '| --- | --- | ---: |',
    ]
    for item in sequence['transaction_semantics']:
        engine = item['engine']
        restored = 'Yes' if item['rollback_restored'] else 'No'
        remaining = 0 if engine == 'memory' else sequence['rows_per_table']
        lines.append(f'| {ENGINE_NAMES[engine]} | {restored} | {remaining:,} |')
    lines += [
        '', 'All four restart tables started with the same row count. MEMORY lost its rows; '
        'the other three retained theirs.', '',
        'The disposable container and volume were removed. See [the transcript](transcript.txt), '
        '[checked results](validation.json) and [command records](commands.json) for details.', '',
    ]
    return '\n'.join(lines)


class StockTutorial:
    def __init__(self, project=None, output=None, expected_arch=None, *, verbose=False):
        self.project = 'cu-stock-' + secrets.token_hex(6) if project is None else project
        validate_project(self.project)  # Before creating files or invoking Docker.
        self.expected_arch = expected_arch
        self.verbose = verbose
        self.stage = 'Docker check'
        self.container_name = self.project + '-db'
        self.volume = self.project + '-data'
        self.owner = secrets.token_hex(16)
        self.passwords = (secrets.token_hex(24), secrets.token_hex(24))
        self.env = dict(os.environ, MARIADB_ROOT_PASSWORD=self.passwords[0],
                        MARIADB_PASSWORD=self.passwords[1])
        stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        self.output = Path(output) if output else ROOT / 'results' / (stamp + '-' + self.project)
        self.container_id = None
        self.volume_created = False
        self.image_id = None
        self.lock = threading.Lock()
        self.records = []
        self.counter = 0
        self.evidence = dict(experiment='stock_tutorial_correctness', status='running',
                             image_reference=IMAGE, project=self.project,
                             host_platform=platform.platform(), host_machine=platform.machine(),
                             host_python=sys.version, commit=os.environ.get('GITHUB_SHA'),
                             source_sha256={}, scope='Four-engine SQL correctness; no performance ranking')

    def redact(self, text):
        for password in self.passwords:
            text = text.replace(password, '[REDACTED]')
        return text

    def progress(self, stage, message):
        self.stage = stage
        print(message, flush=True)

    def log(self, text, *, detail=False):
        text = self.redact(text)
        with self.lock:
            if self.verbose or not detail:
                print(text, flush=True)
            with (self.output / 'transcript.txt').open('a', encoding='utf-8') as stream:
                stream.write(text + '\n')

    def command(self, args, input_text=None, private_output=False, timeout=180):
        with self.lock:
            self.counter += 1
            number = self.counter
        argv = ['docker', *args]
        started = time.monotonic()
        result = subprocess.run(argv, cwd=ROOT, env=self.env, input=input_text, text=True,
                                encoding='utf-8', errors='replace', capture_output=True, timeout=timeout)
        record = dict(number=number, argv=argv, input=input_text, exit_code=result.returncode,
                      stdout='[private inspect output omitted]' if private_output else result.stdout,
                      stderr=result.stderr, elapsed_seconds=round(time.monotonic()-started, 6))
        record = json.loads(self.redact(json.dumps(record)))
        with self.lock:
            self.records.append(record)
        self.log('COMMAND_RECORD ' + json.dumps(record, sort_keys=True), detail=True)
        if result.returncode:
            raise RuntimeError(self.redact(result.stderr.strip() or 'Docker command failed'))
        return result.stdout.strip()

    def inspect_container(self, running=True):
        require(bool(self.container_id), 'No owned tutorial container')
        info = json.loads(self.command(['container', 'inspect', self.container_id], private_output=True))[0]
        labels = info['Config'].get('Labels') or {}
        mounts = [m for m in info['Mounts'] if m['Destination'] == '/var/lib/mysql']
        require(info['Id'] == self.container_id and labels.get(PROJECT_LABEL) == self.project and
                labels.get(OWNER_LABEL) == self.owner, 'Container ownership mismatch; refusing operation')
        require(info['Image'] == self.image_id and info['Config']['Image'] == IMAGE,
                'Unexpected tutorial image')
        require(len(mounts) == 1 and mounts[0].get('Name') == self.volume and
                mounts[0].get('Type') == 'volume', 'Unexpected tutorial database volume')
        require(info['HostConfig']['NetworkMode'] == 'none' and
                not info['HostConfig'].get('PortBindings'), 'Tutorial must not publish a database port')
        if running:
            require(info['State']['Status'] == 'running' and not info['State'].get('OOMKilled'),
                    'Tutorial database is not running normally')
        return info

    def inspect_volume(self):
        info = json.loads(self.command(['volume', 'inspect', self.volume], private_output=True))[0]
        labels = info.get('Labels') or {}
        require(info['Name'] == self.volume and labels.get(PROJECT_LABEL) == self.project and
                labels.get(OWNER_LABEL) == self.owner, 'Volume ownership mismatch; refusing operation')
        return info

    def wait_healthy(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            info = self.inspect_container(running=False)
            require(info['State']['Status'] == 'running' and not info['State'].get('OOMKilled'),
                    'Tutorial server exited or was OOM-killed')
            health = info['State'].get('Health', {}).get('Status')
            if health == 'healthy':
                return
            require(health in ('starting', 'unhealthy'), 'Expected the official image healthcheck')
            time.sleep(1)
        raise RuntimeError('Timed out waiting for the stock MariaDB healthcheck')

    def start(self):
        self.progress('Docker check', 'Checking Docker...')
        info = json.loads(self.command(['info', '--format',
            '{"os":"{{.OSType}}","architecture":"{{.Architecture}}",'
            '"version":"{{.ServerVersion}}","kernel":"{{.KernelVersion}}",'
            '"cpus":{{.NCPU}},"memory_bytes":{{.MemTotal}}}']))
        require(info['os'] == 'linux', 'Docker must use Linux containers')
        arch = architecture(info['architecture'])
        if self.expected_arch:
            require(arch == self.expected_arch and platform.system() == 'Linux' and
                    architecture(platform.machine()) == arch, 'Expected a native Linux architecture match')
        self.evidence['docker'] = info
        self.evidence['architecture'] = arch
        self.stage = 'resource check'
        existing = self.command(['container', 'ls', '-a', '--filter',
                                 'name=^/' + self.container_name + '$', '--format', '{{.ID}}'])
        require(not existing, 'Container name already exists; refusing to reuse it')
        volumes = self.command(['volume', 'ls', '--format', '{{.Name}}']).splitlines()
        require(self.volume not in volumes, 'Volume name already exists; refusing to reuse it')
        self.progress('image download', 'Fetching the pinned MariaDB image (first download may take a moment)...')
        self.command(['pull', IMAGE], timeout=300)
        image = json.loads(self.command(['image', 'inspect', IMAGE], private_output=True))[0]
        require(image['Os'] == 'linux' and architecture(image['Architecture']) == arch,
                'Image architecture differs from the Docker engine')
        self.image_id = image['Id']
        self.evidence['image'] = {k: image.get(k) for k in ('Id', 'Os', 'Architecture', 'RepoDigests')}
        self.progress('server startup', 'Starting a disposable MariaDB server...')
        labels = ['--label', PROJECT_LABEL+'='+self.project, '--label', OWNER_LABEL+'='+self.owner]
        self.command(['volume', 'create', *labels, self.volume])
        self.inspect_volume()
        self.volume_created = True
        self.container_id = self.command(['container', 'create', '--name', self.container_name,
            *labels, '--network', 'none', '--cpus', '2', '--memory', '1g',
            '--env', 'MARIADB_ROOT_PASSWORD', '--env', 'MARIADB_PASSWORD',
            '--env', 'MARIADB_DATABASE=engine_lab', '--env', 'MARIADB_USER=tutorial',
            '--mount', 'type=volume,src='+self.volume+',dst=/var/lib/mysql',
            '--mount', 'type=bind,src='+str(ROOT/'sql/tutorial')+',dst=/tutorial,readonly',
            '--health-cmd', 'healthcheck.sh --connect --innodb_initialized',
            '--health-interval', '2s', '--health-timeout', '5s', '--health-start-period', '30s',
            '--health-retries', '60', IMAGE])
        self.inspect_container(running=False)
        self.command(['start', self.container_id])
        self.wait_healthy()
        hashes = {}
        for name in COMMON_FILES:
            actual = self.command(['exec', self.container_id, 'sha256sum', '/tutorial/'+name]).split()[0]
            expected = hashlib.sha256((ROOT/'sql/tutorial'/name).read_bytes()).hexdigest()
            require(actual == expected, 'Mounted tutorial source does not match the checkout')
            hashes[name] = actual
        self.evidence['mounted_sql_sha256'] = hashes
        self.evidence['container_id'] = self.container_id

    def sql(self, text):
        return self.command(['exec', '-i', self.container_id, 'sh', '-c', CLIENT], input_text=text+'\n')

    def restart(self):
        self.progress('server restart', 'Restarting MariaDB to check which tables keep their rows...')
        self.inspect_container()
        self.command(['restart', '--time', '30', self.container_id])
        self.wait_healthy()
        self.inspect_container()
        self.stage = 'SQL checks'

    def cleanup(self):
        removed = dict(container_removed=False, volume_removed=False)
        if self.container_id:
            self.inspect_container(running=False)
            self.command(['rm', '-f', self.container_id])
            removed['container_removed'] = True
        if self.volume_created:
            self.inspect_volume()
            self.command(['volume', 'rm', self.volume])
            removed['volume_removed'] = True
        self.evidence['resource_cleanup'] = removed

    def run(self):
        try:
            self.output.mkdir(parents=True, exist_ok=False)
        except FileExistsError as exc:
            raise RuntimeError(f'Output directory already exists: {self.output}. '
                               'Choose a new --output path or omit that option.') from exc
        error = None
        failure = None
        try:
            self.start()
            self.progress('SQL checks', 'Running the four-engine SQL tutorial...')
            version = self.sql('SELECT VERSION();')
            require('MariaDB' in version and version.split('-', 1)[0] == '11.8.9',
                    'Expected the pinned MariaDB 11.8.9')
            self.evidence['server_version'] = version
            require(self.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE();") == '0',
                    'Fresh tutorial database is not empty')
            self.sql("CREATE TABLE ci_tutorial_sentinel (id INT PRIMARY KEY, note VARCHAR(32)); "
                     "INSERT INTO ci_tutorial_sentinel VALUES (1,'preserve');")
            checks = TutorialChecks(self.sql, self.restart)
            self.evidence['sequences'] = [checks.run_sequence(False)]
            require(tuple(checks.sourced_files) == COMMON_FILES, 'Unexpected stock tutorial source sequence')
            self.evidence['sourced_files'] = checks.sourced_files
            self.sql('DROP TABLE ci_tutorial_sentinel;')
        except Exception as exc:
            error = self.redact(str(exc)) or type(exc).__name__
            message = ('Docker was not found. Install Docker or Docker Desktop if needed.'
                       if self.stage == 'Docker check' and isinstance(exc, FileNotFoundError)
                       else f'Stopped during {self.stage}: {error.splitlines()[0]}')
            failure = message + '\nNext: ' + NEXT_STEPS[self.stage]
            if self.container_id:
                try:
                    self.command(['logs', '--tail', '80', self.container_id])
                except Exception as diagnostic_error:
                    self.log('Diagnostic capture failed: '+str(diagnostic_error), detail=True)
        finally:
            try:
                if self.container_id or self.volume_created:
                    self.progress('cleanup', 'Removing the disposable tutorial database...')
                self.cleanup()
            except Exception as exc:
                error = (error + '; ' if error else '') + 'Cleanup: ' + self.redact(str(exc))
                failure = ((failure + '\n' if failure else '') +
                           'Cleanup did not finish. ' + NEXT_STEPS['cleanup'])
        if not error and not all(self.evidence['resource_cleanup'].values()):
            error = 'Disposable resources were not removed'
            failure = error + '. ' + NEXT_STEPS['cleanup']
        self.evidence['status'] = 'failed' if error else 'passed'
        if error:
            self.evidence['error'] = error
        for relative in ('scripts/check_stock_tutorial.py', 'scripts/tutorial_checks.py',
                         'scripts/tutorial_transactions.py',
                         '.github/workflows/correctness.yml'):
            self.evidence['source_sha256'][relative] = hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()
        body = json.dumps(self.evidence, indent=2) + '\n'
        (self.output/'validation.json').write_text(body, encoding='utf-8')
        (self.output/'commands.json').write_text(json.dumps(self.records, indent=2)+'\n', encoding='utf-8')
        self.log('STOCK_TUTORIAL_VALIDATION_JSON_BEGIN\n'+body.rstrip()+'\nSTOCK_TUTORIAL_VALIDATION_JSON_END',
                 detail=True)
        if error:
            raise RuntimeError(f'{failure}\nDiagnostics: {self.output}')
        summary = self.output / 'summary.md'
        summary.write_text(render_summary(self.evidence), encoding='utf-8')
        self.log('MEMORY range: BTREE used an index range; HASH scanned the table.')
        self.log('Rollback: InnoDB undid the transfer; Aria, MyISAM and MEMORY did not.')
        self.log('Restart: InnoDB, Aria and MyISAM kept their rows; MEMORY emptied.')
        self.log('STOCK TUTORIAL PASS: '+self.evidence['architecture'])
        print('Summary:', summary, flush=True)
        print('Saved:', self.output, flush=True)
        return self.evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', help='Disposable project; an unused random name is the default')
    parser.add_argument('--output', type=Path, help='New output directory; existing paths are refused')
    parser.add_argument('--expect-architecture', choices=('amd64', 'arm64'), help='CI native-platform guard')
    parser.add_argument('--verbose', action='store_true',
                        help='Also print the saved command and validation details')
    args = parser.parse_args()
    try:
        StockTutorial(args.project, args.output, args.expect_architecture, verbose=args.verbose).run()
    except Exception as error:
        print('STOCK TUTORIAL FAILED:', str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
