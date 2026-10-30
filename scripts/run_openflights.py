"""Build once and run reviewed OpenFlights stages through immutable image IDs.

Prepare prints a session.json path. Run --pilot, review its summary, then --full
with that same session and power description. --stop retains its database volume.
--smoke exercises only deterministic five-engine correctness and runtime controls.
"""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from benchmarks import openflights as benchmark
from benchmarks.core import dataset_digest
from benchmarks.run import save_json
from benchmarks.telemetry import quota_cpus

PROJECT = re.compile(r'cu-openflights-([0-9a-f]{32})\Z')
IMAGE = re.compile(r'sha256:[0-9a-f]{64}\Z')
RUN_ID = re.compile(r'[0-9]{8}T[0-9]{6}Z-openflights-[0-9a-f]{8}\Z')
OWNER_LABEL = 'cu.openflights.owner'
BEGIN = 'OPENFLIGHTS_CONTROLS_BEGIN'
END = 'OPENFLIGHTS_CONTROLS_END'

# Probes are outside all benchmark timers. The normal harness/JSON stays intact.
WORKER = r'''
import hashlib,json,os,sys,tempfile
from pathlib import Path
import pymysql
from benchmarks import openflights as b
from benchmarks.core import dataset_digest
from benchmarks.run import runtime_metadata,source_fingerprint,variables

def controls():
    manifest,rows=b.load_dataset()
    sources={k.replace(chr(92),'/'):v for k,v in source_fingerprint().items()}
    for p in list((b.ROOT/'sql/openflights').glob('*.sql'))+[b.DATA/'manifest.json',b.ROOT/'scripts/fetch_openflights.py']:
        sources[str(p.relative_to(b.ROOT)).replace(chr(92),'/')]=hashlib.sha256(p.read_bytes()).hexdigest()
    with pymysql.connect(host=os.environ['DB_HOST'],user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],
            database='engine_lab',autocommit=True,charset='utf8mb4',connect_timeout=10) as connection:
        with connection.cursor() as c:
            c.execute("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
            c.execute('SET SESSION query_cache_type=OFF')
            c.execute('SET SESSION max_heap_table_size=134217728')
            c.execute('SELECT VERSION()');version=c.fetchone()[0]
            return dict(source_sha256=sources,runtime=runtime_metadata(),server_version=version,
                        global_variables=variables(c,'global'),session_variables=variables(c,'session'),
                        dataset_sha256=dataset_digest(rows),rows=len(rows))

mode,power,expected_text=sys.argv[1:]
expected=json.loads(expected_text)
with tempfile.TemporaryDirectory(prefix='.openflights-probe-',dir='/results'): pass
before=controls()
if any(before[key]!=expected[key] for key in ('source_sha256','dataset_sha256','rows')):
    raise RuntimeError('Prepared source/dataset differs before workload; refusing execution')
if expected.get('reference') is not None and before!=expected['reference']:
    raise RuntimeError('Runtime/SQL controls changed before workload; refusing execution')
if before['runtime'].get('cgroup_memory_max')!='536870912' or before['runtime'].get('cgroup_cpu_max')!='100000 100000':
    raise RuntimeError('Unexpected worker resource limits before workload')
values=before['session_variables']
if not before['server_version'].startswith('11.8.9-MariaDB'):
    raise RuntimeError('Unexpected server version before workload')
if not (values.get('query_cache_type')=='OFF' and values.get('autocommit')=='ON' and
        values.get('max_heap_table_size')=='134217728' and 'STRICT_ALL_TABLES' in values.get('sql_mode','') and
        'NO_ENGINE_SUBSTITUTION' in values.get('sql_mode','')):
    raise RuntimeError('Unexpected SQL controls before workload')
if mode=='smoke':
    from scripts import check_environment
    check_environment.main()
else:
    b.run(b.Config(pilot=mode=='pilot'),Path('/results'),power)
after=controls()
print('OPENFLIGHTS_CONTROLS_BEGIN')
print(json.dumps(dict(before=before,after=after)))
print('OPENFLIGHTS_CONTROLS_END')
'''


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def execute(argv, capture=False):
    result = subprocess.run(argv, cwd=ROOT, check=True, text=True, encoding='utf-8',
                            errors='replace', stdout=subprocess.PIPE if capture else None)
    return result.stdout.strip() if capture else None


def local_docker_endpoint():
    """Match Docker CLI selector precedence without recording endpoint URLs."""
    context = os.environ.get('DOCKER_CONTEXT')
    endpoint = os.environ.get('DOCKER_HOST') if not context else None
    if not endpoint:
        context = context or execute(['docker', 'context', 'show'], True)
        endpoint = json.loads(execute(['docker', 'context', 'inspect', context, '--format',
                                       '{{json .Endpoints.docker.Host}}'], True))
    require(isinstance(endpoint, str) and endpoint.startswith(('unix://', 'npipe://')),
            'Use a local unix/npipe Docker endpoint; remote/TCP daemons cannot mount this checkout')
    return endpoint.split(':', 1)[0]


def source_hashes():
    paths = [ROOT/name for name in ('Dockerfile', 'requirements.txt', 'compose.yaml',
                                    'compose.runner-2cpu.yaml', 'scripts/fetch_openflights.py',
                                    'data/openflights/manifest.json')]
    for directory in ('benchmarks', 'sql/benchmark', 'docker/mariadb', 'sql/openflights'):
        paths += [p for p in (ROOT/directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    return {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(set(paths))}


def host_identity():
    def git(*args):
        try:
            return subprocess.check_output(['git', *args], cwd=ROOT, text=True,
                                           stderr=subprocess.DEVNULL).strip()
        except (OSError, subprocess.CalledProcessError):
            return 'unavailable (source archive)'
    return dict(commit=git('rev-parse', 'HEAD'), tracked_status=git('status', '--porcelain', '--untracked-files=no'),
                launcher_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())


def expected_runtime(session):
    return dict(services={role: dict(image=session['images'][role],
        labels={OWNER_LABEL: session['token']}) for role in ('db', 'runner')},
        volumes=dict(db_data=dict(labels={OWNER_LABEL: session['token']})))


def validate_session(session, path):
    match = PROJECT.fullmatch(session.get('project', ''))
    require(match is not None and match[1] == session.get('token'), 'Invalid isolated session identity')
    require(session.get('format_version') == 1 and session.get('experiment') == 'immutable_openflights_v1',
            'Unsupported session manifest')
    require(set(session.get('images', {})) == {'db', 'runner'} and
            all(IMAGE.fullmatch(value) for value in session['images'].values()), 'Invalid selected image IDs')
    require(path.parent.parent.resolve() == (ROOT/'results').resolve() and path.name == 'session.json',
            'Session must remain in this checkout results directory')
    runtime = path.parent/'runtime-images.compose.json'
    require(json.loads(runtime.read_text(encoding='utf-8')) == expected_runtime(session),
            'Frozen runtime override changed')


def load_session(path):
    path = Path(path).resolve()
    session = json.loads(path.read_text(encoding='utf-8'))
    validate_session(session, path)
    return session, path


@contextmanager
def operation_lock(path):
    lock = path.parent/'.operation.lock'
    try:
        with lock.open('x', encoding='utf-8') as stream:
            stream.write('An OpenFlights session operation is active. Inspect before removing a stale lock.\n')
    except FileExistsError as exc:
        raise RuntimeError('Session operation already active; inspect any stale lock before retrying') from exc
    try:
        yield
    finally:
        lock.unlink()


def compose(session, path, *args, capture=False, overrides=()):
    require(PROJECT.fullmatch(session['project']) is not None, 'Only isolated OpenFlights projects allowed')
    argv = ['docker', 'compose', '--env-file', str(ROOT/'.env'), '-f', str(ROOT/'compose.yaml')]
    for override in overrides:
        argv += ['-f', str(override)]
    argv += ['-p', session['project'], *args]
    session.setdefault('commands', []).append(argv)
    save_json(path, session)
    return execute(argv, capture)


def ensure_new(project):
    require(PROJECT.fullmatch(project) is not None, 'Invalid isolated OpenFlights project')
    for resource in ('container', 'volume', 'network'):
        args = ['docker', resource, 'ls', '-q', '--filter', 'label=com.docker.compose.project='+project]
        if resource == 'container':
            args.append('-a')
        require(not execute(args, True), 'Pre-existing project resources; refusing reuse')
    require(project+'_db_data' not in execute(['docker', 'volume', 'ls', '--format', '{{.Name}}'], True).splitlines(),
            'Database volume name already exists; refusing reuse')


def prepare(build_override=None):
    endpoint_kind = local_docker_endpoint()
    require((ROOT/'.env').is_file(), 'Run setup first; existing .env credentials are required and preserved')
    require(execute(['docker', 'info', '--format', '{{.OSType}}/{{.Architecture}}'], True)
            in ('linux/amd64', 'linux/x86_64'), 'Linux amd64 Docker engine required')
    if build_override is not None:
        build_override = Path(build_override).resolve()
        require(build_override.is_file(), 'Build adapter not found')
    manifest, rows = benchmark.load_dataset()
    token = uuid.uuid4().hex
    project = 'cu-openflights-'+token
    ensure_new(project)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    directory = ROOT/'results'/(stamp+'-openflights-session-'+token[:8])
    directory.mkdir(parents=True, exist_ok=False)
    path = directory/'session.json'
    session = dict(format_version=1, experiment='immutable_openflights_v1', token=token, project=project,
        status='preparing', stages={}, host=host_identity(), source_sha256=source_hashes(),
        dataset_sha256=dataset_digest(rows), rows=len(rows), commands=[], power_condition=None,
        compose_version=execute(['docker', 'compose', 'version', '--short'], True),
        image_binding='immutable-session-v1', volume_policy='retain; no volume deletion commands')
    session['docker_endpoint_kind'] = endpoint_kind
    save_json(path, session)
    try:
        tags = {role: project+'-'+role+':local' for role in ('db', 'runner')}
        for tag in tags.values():
            require(not execute(['docker', 'image', 'ls', '-q', '--filter', 'reference='+tag], True),
                    'Per-session build tag exists; refusing overwrite')
        build_file = directory/'build-images.compose.json'
        save_json(build_file, dict(services={role: dict(image=tag) for role, tag in tags.items()}))
        overrides = ([build_override] if build_override is not None else [])+[build_file]
        if build_override is not None:
            session['build_adapter_sha256'] = hashlib.sha256(build_override.read_bytes()).hexdigest()
        compose(session, path, 'build', 'db', 'runner', overrides=overrides)
        session['images'] = {}
        for role, tag in tags.items():
            info = json.loads(execute(['docker', 'image', 'inspect', '--format',
                '{"id":"{{.Id}}","os":"{{.Os}}","architecture":"{{.Architecture}}"}', tag], True))
            require(IMAGE.fullmatch(info['id']) and info['os'] == 'linux' and info['architecture'] == 'amd64',
                    'Unexpected built image identity/platform')
            session['images'][role] = info['id']
        save_json(directory/'runtime-images.compose.json', expected_runtime(session))
        session['status'] = 'prepared'
        save_json(path, session)
    except BaseException as error:
        session.update(status='failed', error_type=type(error).__name__)
        save_json(path, session)
        raise
    print('Prepared immutable images. Session:', path, flush=True)
    print('Run --pilot, review its summary, then --full using this session and the same power description.')
    return path


def identity(session, path, role):
    runtime = path.parent/'runtime-images.compose.json'
    container = compose(session, path, 'ps', '-a', '-q', role, capture=True, overrides=[runtime])
    require(bool(container) and len(container.splitlines()) == 1, 'Expected one owned '+role+' container')
    info = json.loads(execute(['docker', 'inspect', container], True))[0]
    labels = info['Config'].get('Labels') or {}
    require(labels.get('com.docker.compose.project') == session['project'] and
            labels.get('com.docker.compose.service') == role and labels.get(OWNER_LABEL) == session['token'],
            'Container ownership mismatch; refusing operation')
    require(info['Image'] == session['images'][role] and info['Config']['Image'] == session['images'][role],
            'Container image differs from immutable selection')
    wanted_cpus, wanted_memory = (2000000000, 2147483648) if role == 'db' else (1000000000, 536870912)
    require(info['HostConfig']['NanoCpus'] == wanted_cpus and info['HostConfig']['Memory'] == wanted_memory,
            'Container CPU/memory controls differ')
    if role == 'db':
        mounts = [m for m in info['Mounts'] if m['Destination'] == '/var/lib/mysql']
        require(len(mounts) == 1 and mounts[0].get('Name') == session['project']+'_db_data' and
                mounts[0]['Type'] == 'volume', 'Unexpected database volume')
        require(not info['HostConfig'].get('PortBindings'), 'Database must not publish a host port')
        volume = json.loads(execute(['docker', 'volume', 'inspect', mounts[0]['Name']], True))[0]
        volume_labels = volume.get('Labels') or {}
        require(volume_labels.get('com.docker.compose.project') == session['project'] and
                volume_labels.get(OWNER_LABEL) == session['token'], 'Database volume ownership mismatch')
    else:
        mounts = [m for m in info['Mounts'] if m['Destination'] == '/results']
        require(len(mounts) == 1 and mounts[0]['Type'] == 'bind' and mounts[0].get('RW'),
                'Expected writable results bind mount')
    return info


def recorded_identity(info):
    return dict(container_id=info['Id'], image_id=info['Image'], selected_reference=info['Config']['Image'],
        memory_bytes=info['HostConfig']['Memory'], nano_cpus=info['HostConfig']['NanoCpus'],
        ownership_labels={key: (info['Config'].get('Labels') or {}).get(key)
                          for key in ('com.docker.compose.project', 'com.docker.compose.service', OWNER_LABEL)},
        mounts=[{key: mount.get(key) for key in ('Type', 'Name', 'Destination', 'RW')}
                for mount in info['Mounts']],
        state={key: info['State'].get(key) for key in ('Status', 'ExitCode', 'OOMKilled', 'StartedAt', 'FinishedAt')})


def validate_controls(observed, session):
    require(set(observed) == {'before', 'after'} and observed['before'] == observed['after'],
            'Worker controls changed during execution')
    current = observed['before']
    require(current['source_sha256'] == session['source_sha256'], 'Worker source differs from prepared source')
    require(current['dataset_sha256'] == session['dataset_sha256'] and current['rows'] == session['rows'],
            'Worker dataset differs')
    runtime = current['runtime']
    require(quota_cpus(runtime.get('cgroup_cpu_max', '')) == 1 and runtime.get('cgroup_memory_max') == '536870912',
            'Worker CPU/memory limits differ')
    require(current['server_version'].startswith('11.8.9-MariaDB'), 'Unexpected server version')
    values = current['session_variables']
    require(values.get('query_cache_type') == 'OFF' and values.get('autocommit') == 'ON' and
            values.get('max_heap_table_size') == '134217728' and
            'STRICT_ALL_TABLES' in values.get('sql_mode', '') and
            'NO_ENGINE_SUBSTITUTION' in values.get('sql_mode', ''), 'Worker SQL controls differ')
    require(not session.get('control_reference') or session['control_reference'] == current,
            'Source/runtime/SQL controls changed between stages')
    return current


def read_result(output, mode, session):
    matches = re.findall(r'^Saved: /results/([^\r\n]+)$', output, re.M)
    require(len(matches) == 1 and RUN_ID.fullmatch(matches[0]), 'Worker did not report one valid result directory')
    directory = ROOT/'results'/matches[0]
    result = json.loads((directory/'results.json').read_text(encoding='utf-8'))
    require(result['run_id'] == matches[0] and result['config'] == vars(benchmark.Config(pilot=mode == 'pilot')),
            'Unexpected OpenFlights run/configuration')
    require(result['dataset_sha256'] == session['dataset_sha256'] and result['rows'] == session['rows'],
            'Result dataset differs')
    require(result['source_sha256'] == session['source_sha256'] and result['power_condition'] == session['power_condition'],
            'Result source/power differs')
    for field in ('runtime', 'server_version', 'global_variables', 'session_variables'):
        require(result[field] == session['control_reference'][field], 'Result differs from runtime probe: '+field)
    require(benchmark.summarize(result) == result['statistics'], 'Recorded statistics differ')
    require((directory/'summary.md').read_text(encoding='utf-8') == benchmark.markdown(result),
            'Recorded summary differs')
    return dict(run_id=matches[0], results_sha256=hashlib.sha256((directory/'results.json').read_bytes()).hexdigest(),
                summary_sha256=hashlib.sha256((directory/'summary.md').read_bytes()).hexdigest())


def check_pilot(session):
    pilot = session['stages'].get('pilot', {})
    require(pilot.get('status') == 'completed', 'Complete and review the pilot before full')
    result = pilot['result']
    require(RUN_ID.fullmatch(result['run_id']) is not None, 'Invalid pilot run identity')
    directory = ROOT/'results'/result['run_id']
    for name, field in (('results.json', 'results_sha256'), ('summary.md', 'summary_sha256')):
        require(hashlib.sha256((directory/name).read_bytes()).hexdigest() == result[field],
                'Pilot evidence changed; inspect before full')


def start_database(session, path):
    runtime = path.parent/'runtime-images.compose.json'
    existing = compose(session, path, 'ps', '-a', '-q', 'db', capture=True, overrides=[runtime])
    if existing:
        info = identity(session, path, 'db')
        require(info['State']['Status'] == 'running', 'Database stopped/restarted; prepare a fresh measurement session')
        require(info['Id'] == session.get('database', {}).get('container_id'), 'Database container changed')
        require(info['State']['StartedAt'] == session.get('database', {}).get('state', {}).get('StartedAt'),
                'Database restarted since pilot/preparation')
    else:
        require(not session.get('database'), 'Prepared database disappeared; refusing recreation')
        compose(session, path, 'up', '-d', '--no-build', '--pull', 'never', '--no-recreate',
                '--wait', '--wait-timeout', '180', 'db', overrides=[runtime])
        info = identity(session, path, 'db')
        require(info['State']['Status'] == 'running', 'Database did not start normally')
    session['database'] = recorded_identity(info)
    save_json(path, session)


def run_worker(session, path, mode, power):
    runtime = path.parent/'runtime-images.compose.json'
    require(not compose(session, path, 'ps', '-a', '-q', 'runner', capture=True, overrides=[runtime]),
            'Pre-existing worker; refusing recreation or retry')
    command_file = path.parent/(mode+'-command.compose.json')
    expected = {key: session[key] for key in ('source_sha256', 'dataset_sha256', 'rows')}
    expected['reference'] = session.get('control_reference')
    save_json(command_file, dict(services=dict(runner=dict(command=['python', '-c', WORKER, mode, power,
                                                                 json.dumps(expected)]))))
    overrides = [runtime, command_file]
    compose(session, path, 'create', '--no-build', '--pull', 'never', '--no-recreate', 'runner', overrides=overrides)
    before = identity(session, path, 'runner')
    require(before['State']['Status'] == 'created', 'Worker was already started; refusing reuse')
    session['stages'][mode]['runner_before'] = recorded_identity(before)
    save_json(path, session)
    argv = ['docker', 'start', '--attach', before['Id']]
    session['commands'].append(argv)
    save_json(path, session)
    process = subprocess.run(argv, cwd=ROOT, text=True, encoding='utf-8', errors='replace',
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    output = process.stdout or ''
    (path.parent/(mode+'-transcript.txt')).write_text(output, encoding='utf-8')
    print(output, end='', flush=True)
    after = identity(session, path, 'runner')
    session['stages'][mode]['runner_after'] = recorded_identity(after)
    save_json(path, session)
    require(process.returncode == 0 and after['Id'] == before['Id'] and
            after['State']['Status'] == 'exited' and after['State']['ExitCode'] == 0 and
            not after['State'].get('OOMKilled'), 'Worker failed; container and partial evidence retained')
    require(output.count(BEGIN) == 1 and output.count(END) == 1, 'Missing worker control record')
    observed = json.loads(output.split(BEGIN, 1)[1].split(END, 1)[0].strip())
    session['control_reference'] = validate_controls(observed, session)
    session['stages'][mode]['controls'] = observed
    if mode != 'smoke':
        session['stages'][mode]['result'] = read_result(output, mode, session)
    database = identity(session, path, 'db')
    session['stages'][mode]['database_after'] = recorded_identity(database)
    save_json(path, session)
    require(database['Id'] == session['database']['container_id'] and
            database['State']['Status'] == 'running' and not database['State'].get('OOMKilled') and
            database['State']['StartedAt'] == session['database']['state']['StartedAt'],
            'Database restarted/replaced during worker; retain evidence and inspect')
    # Preserve failed workers; remove only the same successful, verified container.
    execute(['docker', 'rm', after['Id']], True)


def stop(session, path):
    runtime = path.parent/'runtime-images.compose.json'
    if not compose(session, path, 'ps', '-a', '-q', 'db', capture=True, overrides=[runtime]):
        require(not session.get('database'), 'Recorded database disappeared; inspect session')
        return
    identity(session, path, 'db')
    compose(session, path, 'stop', '-t', '120', 'db', overrides=[runtime])
    info = identity(session, path, 'db')
    require(info['State']['Status'] == 'exited' and info['State']['ExitCode'] == 0 and
            not info['State'].get('OOMKilled'), 'Unclean database stop; retain volume and inspect')
    session['database_stop'] = recorded_identity(info)
    save_json(path, session)


def run_stage(path, mode, power=None):
    session, path = load_session(path)
    with operation_lock(path):
        # Reload after locking so a preceding process cannot leave stale state.
        session, path = load_session(path)
        require(local_docker_endpoint() == session.get('docker_endpoint_kind'),
                'Docker endpoint kind changed since preparation; restore the local session endpoint')
        if mode == 'stop':
            stop(session, path)
            print('Database stopped; credentials, evidence and database volume retained.')
            return
        require(session['status'] in ('prepared', 'pilot_completed'), 'Session not ready; failed/completed sessions cannot be retried')
        require(mode not in session['stages'], 'Stage already attempted; inspect retained evidence, do not retry')
        require(source_hashes() == session['source_sha256'] and host_identity() == session['host'],
                'Host source/revision changed since preparation; prepare a fresh session')
        require(isinstance(power, str) and bool(power.strip()), 'Record the actual power condition')
        if mode == 'full':
            check_pilot(session)
            require(power == session['power_condition'], 'Power description changed between pilot and full')
            session['pilot_review_acknowledged'] = True
        else:
            require(session['status'] == 'prepared', 'Start a separate session for smoke or pilot')
            session['power_condition'] = power
        session['stages'][mode] = dict(status='running')
        session['status'] = mode+'_running'
        save_json(path, session)
        try:
            start_database(session, path)
            run_worker(session, path, mode, power)
            session['stages'][mode]['status'] = 'completed'
            session['status'] = 'pilot_completed' if mode == 'pilot' else 'completed'
            save_json(path, session)
            if mode == 'smoke':
                stop(session, path)
                print('OPENFLIGHTS SMOKE PASS: actual images and five-engine correctness verified; no benchmark run.')
            elif mode == 'pilot':
                print('Pilot passed. Review its raw results/summary before invoking --full.')
            else:
                print('Full run passed. Use --stop with this session to retain its database volume.')
        except BaseException as error:
            session['status'] = 'failed'
            session['stages'][mode].update(status='failed', error_type=type(error).__name__)
            save_json(path, session)
            print('Failed isolated session retained:', path, file=sys.stderr)
            print('Inspect its logs, container and table before stopping; no retry or volume deletion was performed.', file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    for mode in ('prepare', 'pilot', 'full', 'stop', 'smoke'):
        modes.add_argument('--'+mode, action='store_true')
    parser.add_argument('--session', type=Path, help='Prepared results/.../session.json')
    parser.add_argument('--power-condition', help='Actual conditions; identical description required across pilot/full')
    parser.add_argument('--build-override', type=Path, help='Build-only proxy/CA adapter; runtime always uses frozen IDs')
    args = parser.parse_args()
    mode = next(mode for mode in ('prepare', 'pilot', 'full', 'stop', 'smoke') if getattr(args, mode))
    try:
        require(not args.build_override or mode in ('prepare', 'smoke') and args.session is None,
                'A build adapter is accepted only for preparation, never between stages')
        if mode == 'prepare':
            require(args.session is None, 'Preparation creates a fresh session')
            prepare(args.build_override)
        else:
            require(args.session is not None or mode == 'smoke', 'This operation requires --session')
            path = args.session or prepare(args.build_override)
            run_stage(path, mode, args.power_condition or ('correctness smoke only; not performance evidence' if mode == 'smoke' else None))
    except (Exception, KeyboardInterrupt) as error:
        print('FAILED:', str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
