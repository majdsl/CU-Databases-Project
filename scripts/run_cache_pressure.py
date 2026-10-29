"""Host-only orchestrator for disposable InnoDB cache-pressure trials."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import zlib

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import cache_pressure as benchmark
from benchmarks.run import save_json

PATTERN=re.compile(r'cu-pressure-[0-9a-f]{32}-[0-9]+\Z')


def execute(argv,capture=False):
    r=subprocess.run(argv,cwd=ROOT,check=True,text=True,encoding='utf-8',errors='replace',
                     stdout=subprocess.PIPE if capture else None)
    return r.stdout.strip() if capture else None


def compose(project,*args,capture=False,overrides=()):
    if not PATTERN.fullmatch(project):raise ValueError('Only unique isolated experiment projects are allowed')
    argv=['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'compose.cache-pressure.yaml')]
    for override in overrides:argv+=['-f',str(override)]
    return execute(argv+['-p',project,*args],capture)


def ensure_new(project):
    if not PATTERN.fullmatch(project):raise ValueError('Invalid project')
    for resource in ('container','volume','network'):
        args=['docker',resource,'ls','-q','--filter','label=com.docker.compose.project='+project]
        if resource=='container':args.append('-a')
        if execute(args,True):raise RuntimeError('Pre-existing resources; refusing reuse')


def identity(project,expected_image=None,service='db'):
    container=compose(project,'ps','-a','-q',service,capture=True)
    if not container or len(container.splitlines())!=1:raise RuntimeError('Expected one isolated '+service)
    details=json.loads(execute(['docker','inspect',container],True))[0]
    labels=details['Config'].get('Labels') or {}
    if labels.get('com.docker.compose.project')!=project or labels.get('com.docker.compose.service')!=service:
        raise RuntimeError('Container ownership mismatch')
    if expected_image is not None and (details['Image']!=expected_image or details['Config']['Image']!=expected_image):
        raise RuntimeError('Container image differs from frozen selection')
    if service=='db':
        mounts=[m for m in details['Mounts'] if m['Destination']=='/var/lib/mysql']
        if len(mounts)!=1 or mounts[0].get('Name')!=project+'_pressure_data':
            raise RuntimeError('Unexpected database volume')
    return details


IMAGE_ID=re.compile(r'sha256:[0-9a-f]{64}\Z')
# Probes surround the existing worker without altering its throughput/read timers.
# They do add work to the broader Docker-launch/DB-CPU observation window.
WORKER_PROGRAM="""
import json,sys
from benchmarks import WORKER_MODULE as worker
from benchmarks import concurrency
from benchmarks.run import runtime_metadata,source_fingerprint,variables

def controls():
    with concurrency.connect() as connection:
        with connection.cursor() as cursor:
            concurrency.configure(cursor)
            cursor.execute('SELECT VERSION()')
            return dict(runtime=runtime_metadata(),source_sha256=source_fingerprint(),
                        server_version=cursor.fetchone()[0],global_variables=variables(cursor,'global'),
                        session_variables=variables(cursor,'session'))

before=controls()
result=WORKER_CALL
result['execution_controls']=dict(before=before,after=controls())
print(json.dumps(result,default=str))
""".replace('WORKER_MODULE','cache_pressure').replace('WORKER_CALL','worker.one_trial(sys.argv[1],int(sys.argv[2]),int(sys.argv[3]))')


def worker_source():
    from benchmarks.run import source_fingerprint
    return {name.replace(chr(92),'/'):digest for name,digest in source_fingerprint().items()}


def build_images(project,directory,token,build_override=None):
    tags={role:'cu-pressure-'+token+'-'+role+':local' for role in ('db','runner')}
    for tag in tags.values():
        if execute(['docker','image','ls','-q','--filter','reference='+tag],True):
            raise RuntimeError('Per-run image tag already exists; refusing overwrite')
    build_file=directory/'build-images.compose.json'
    save_json(build_file,dict(services={role:dict(image=tag) for role,tag in tags.items()}))
    overrides=([Path(build_override)] if build_override is not None else [])+[build_file]
    compose(project,'build','db','runner',overrides=overrides)
    images={}
    for role,tag in tags.items():
        info=json.loads(execute(['docker','image','inspect','--format',
            '{"id":"{{.Id}}","os":"{{.Os}}","architecture":"{{.Architecture}}"}',tag],True))
        if not IMAGE_ID.fullmatch(info['id']) or info['os']!='linux' or info['architecture']!='amd64':
            raise RuntimeError('Unexpected built image identity/platform')
        images[role]=info['id']
    runtime_file=directory/'runtime-images.compose.json'
    save_json(runtime_file,dict(services={role:dict(image=value) for role,value in images.items()}))
    return images,runtime_file


def validate_controls(observed,expected_source,reference=None):
    from benchmarks.telemetry import quota_cpus
    if set(observed)!= {'before','after'} or observed['before']!=observed['after']:
        raise RuntimeError('Worker controls changed during execution')
    current=observed['before']
    if current['source_sha256']!=expected_source:
        raise RuntimeError('Worker source differs from selected host source')
    runtime=current['runtime']
    if (quota_cpus(runtime.get('cgroup_cpu_max',''))!=1 or
            runtime.get('cgroup_memory_max')!='536870912'):
        raise RuntimeError('Worker CPU/memory limit differs from experiment')
    if not current['server_version'].startswith('11.8.9-MariaDB'):
        raise RuntimeError('Unexpected server version')
    if reference is not None and current!=reference:
        raise RuntimeError('Runtime, source or SQL settings changed between workers')
    return current


def run_worker(project,directory,name,arguments,images,runtime_file,expected_source,reference=None):
    if compose(project,'ps','-a','-q','runner',capture=True):
        raise RuntimeError('Existing worker container; refusing recreation')
    command_file=directory/(name+'.compose.json')
    save_json(command_file,dict(services=dict(runner=dict(command=['python','-c',WORKER_PROGRAM,*arguments]))))
    overrides=[runtime_file,command_file]
    # create supports --no-build (run does not). Inspect before starting any code.
    compose(project,'create','--no-build','--pull','never','--no-recreate','runner',overrides=overrides)
    created=identity(project,images['runner'],'runner')
    if created['State']['Status']!='created':raise RuntimeError('Refusing pre-existing worker state')
    process=subprocess.run(['docker','start','--attach',created['Id']],cwd=ROOT,text=True,
        encoding='utf-8',errors='replace',stdout=subprocess.PIPE)
    (directory/(name+'.json')).write_text(process.stdout,encoding='utf-8')
    process.check_returncode()
    finished=identity(project,images['runner'],'runner')
    if (finished['Id']!=created['Id'] or finished['State']['Status']!='exited' or
            finished['State']['ExitCode']!=0 or finished['State'].get('OOMKilled')):
        raise RuntimeError('Worker did not complete normally; retaining container')
    result=json.loads(process.stdout)
    validate_controls(result['execution_controls'],expected_source,reference)
    execute(['docker','rm',created['Id']],True)
    return result


def stop_cleanly(project):
    identity(project)
    compose(project,'stop','-t','120','db')
    state=identity(project)['State']
    if state.get('Status')!='exited' or state.get('ExitCode')!=0 or state.get('OOMKilled'):
        raise RuntimeError('Unclean stop; retain evidence and volume')
    return {k:state.get(k) for k in ('Status','ExitCode','OOMKilled','FinishedAt')}


def expected_data(rows):
    digest=hashlib.sha256();total=0
    for key in range(1,rows+1):
        value=benchmark.payload(key);benchmark.digest_update(digest,key,value);total+=zlib.crc32(value)
    return {'dataset_sha256':digest.hexdigest(),'crc32_sum':total}


def run(mode,power,build_override=None):
    benchmark.settings(mode)
    if not power.strip():raise ValueError('Record actual power conditions')
    if not (ROOT/'.env').is_file():raise ValueError('Existing .env required; run setup first')
    if execute(['docker','info','--format','{{.OSType}}/{{.Architecture}}'],True) not in ('linux/x86_64','linux/amd64'):
        raise RuntimeError('Linux amd64 Docker engine required')
    if build_override is not None and not Path(build_override).is_file():raise ValueError('Build override file not found')
    expected_source=worker_source()
    token=uuid.uuid4().hex
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-cache-pressure-'+token[:8]
    directory=ROOT/'results'/run_id;directory.mkdir(parents=True,exist_ok=False)
    result=dict(format_version=1,experiment='isolated_innodb_cache_pressure_v1',run_id=run_id,mode=mode,
                power_condition=power,status='running',schedule=benchmark.schedule(mode),trials=[],
                compose_version=execute(['docker','compose','version','--short'],True),host_python=sys.version,
                source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                    ('scripts/run_cache_pressure.py','compose.cache-pressure.yaml','benchmarks/cache_pressure.py')})
    result['image_binding']='immutable-per-run-v1'
    result['expected_worker_source_sha256']=expected_source
    result['control_probe_scope']='before/after worker; outside worker timers, included in Docker-launch/DB-CPU window'
    if build_override is not None:
        result['build_override']=dict(path=str(Path(build_override).resolve()),sha256=hashlib.sha256(Path(build_override).read_bytes()).hexdigest())
    path=directory/'results.json';save_json(path,result)
    expected={n:expected_data(n) for n in benchmark.settings(mode)['sizes']}
    result['expected_data']={str(n):v for n,v in expected.items()};save_json(path,result)
    current=None;reference=None;trial_reference=None
    images=None;runtime_file=None
    try:
        for number,item in enumerate(result['schedule'],1):
            project=f'cu-pressure-{token}-{number}';ensure_new(project)
            current=project;result['active_project']=project;result['active_trial']=item;save_json(path,result)
            print('Cache pressure:',item,flush=True)
            if number==1:
                images,runtime_file=build_images(project,directory,token,build_override)
                result['images']=images;save_json(path,result)
            compose(project,'up','-d','--no-build','--pull','never','--no-recreate','--wait','--wait-timeout','180','db',overrides=[runtime_file])
            details=identity(project,images['db'])
            trial=run_worker(project,directory,f'trial-{number:02d}',[mode,str(item['rows']),str(item['round'])],
                images,runtime_file,expected_source,reference)
            reference=validate_controls(trial['execution_controls'],expected_source,reference)
            result['control_reference']=reference
            fields=('source_sha256','runtime','server_version','global_variables','session_variables',
                    'innodb_settings','actual_ddl','innodb_page_size','buffer_pool_bytes')
            selected={key:trial[key] for key in fields}
            if trial['source_sha256']!=expected_source:raise RuntimeError('Worker-reported source differs')
            if trial_reference is not None and selected!=trial_reference:
                raise RuntimeError('Cache-pressure trial source/runtime/SQL settings changed')
            trial_reference=selected
            # Raw output is already preserved by run_worker before validation.
            benchmark.validate_trial(trial,mode,item)
            if any(trial[k]!=v for k,v in expected[item['rows']].items()):raise RuntimeError('Host/worker data mismatch')
            trial.update(position=item['position'],project=project,db_image_id=details['Image'],runner_image_id=images['runner'])
            result['trials'].append(trial);save_json(path,result)
            identity(project,images['db'])
            trial['clean_stop']=stop_cleanly(project);save_json(path,result)
            compose(project,'down','--volumes','--timeout','120')
            current=None;result.pop('active_project');result.pop('active_trial');save_json(path,result)
        result['status']='completed';result['statistics']=benchmark.summary(result)
        report=benchmark.markdown(result);(directory/'summary.md').write_text(report,encoding='utf-8')
        save_json(path,result);print(report);print('Saved:',directory)
    except BaseException as error:
        result['status']='failed';result['error_type']=type(error).__name__
        if current:
            try:
                logs=compose(current,'logs','--no-color','--tail','100','db',capture=True)
                (directory/'failure-db.log').write_text(logs+'\n',encoding='utf-8')
                compose(current,'stop','-t','120','db')
            except BaseException:result['stop_on_failure']='failed; inspect isolated project'
        (directory/'summary.md').unlink(missing_ok=True);save_json(path,result)
        print('Partial results:',directory,file=sys.stderr)
        print('Failed isolated project retained:',current,file=sys.stderr)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    for mode in ('pilot','full','smoke'):m.add_argument('--'+mode,action='store_true')
    p.add_argument('--power-condition',required=True)
    p.add_argument('--build-override',type=Path,help='Optional Compose build adapter; runtime uses only frozen images and standard experiment settings')
    a=p.parse_args()
    try:run('pilot' if a.pilot else 'full' if a.full else 'smoke',a.power_condition,a.build_override)
    except (Exception,KeyboardInterrupt) as error:
        print('FAILED:',str(error),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
