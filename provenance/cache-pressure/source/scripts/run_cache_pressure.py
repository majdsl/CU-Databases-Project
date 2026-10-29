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


def compose(project,*args,capture=False):
    if not PATTERN.fullmatch(project):raise ValueError('Only unique isolated pressure projects are allowed')
    return execute(['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'compose.cache-pressure.yaml'),
                    '-p',project,*args],capture)


def ensure_new(project):
    if not PATTERN.fullmatch(project):raise ValueError('Invalid project')
    for resource in ('container','volume','network'):
        args=['docker',resource,'ls','-q','--filter','label=com.docker.compose.project='+project]
        if resource=='container':args.append('-a')
        if execute(args,True):raise RuntimeError('Pre-existing resources; refusing reuse')


def identity(project):
    container=compose(project,'ps','-a','-q','db',capture=True)
    if not container or len(container.splitlines())!=1:raise RuntimeError('Expected one isolated database')
    details=json.loads(execute(['docker','inspect',container],True))[0]
    if details['Config']['Labels'].get('com.docker.compose.project')!=project:
        raise RuntimeError('Database label mismatch')
    mounts=[m for m in details['Mounts'] if m['Destination']=='/var/lib/mysql']
    if len(mounts)!=1 or mounts[0].get('Name')!=project+'_pressure_data':
        raise RuntimeError('Unexpected database volume')
    return details


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


def run(mode,power):
    benchmark.settings(mode)
    if not power.strip():raise ValueError('Record actual power conditions')
    if not (ROOT/'.env').is_file():raise ValueError('Existing .env required; run setup first')
    if execute(['docker','info','--format','{{.OSType}}/{{.Architecture}}'],True) not in ('linux/x86_64','linux/amd64'):
        raise RuntimeError('Linux amd64 Docker engine required')
    token=uuid.uuid4().hex
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-cache-pressure-'+token[:8]
    directory=ROOT/'results'/run_id;directory.mkdir(parents=True,exist_ok=False)
    result=dict(format_version=1,experiment='isolated_innodb_cache_pressure_v1',run_id=run_id,mode=mode,
                power_condition=power,status='running',schedule=benchmark.schedule(mode),trials=[],
                compose_version=execute(['docker','compose','version','--short'],True),host_python=sys.version,
                source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                    ('scripts/run_cache_pressure.py','compose.cache-pressure.yaml','benchmarks/cache_pressure.py')})
    path=directory/'results.json';save_json(path,result)
    expected={n:expected_data(n) for n in benchmark.settings(mode)['sizes']}
    result['expected_data']={str(n):v for n,v in expected.items()};save_json(path,result)
    current=None
    try:
        for number,item in enumerate(result['schedule'],1):
            project=f'cu-pressure-{token}-{number}';ensure_new(project)
            current=project;result['active_project']=project;result['active_trial']=item;save_json(path,result)
            print('Cache pressure:',item,flush=True)
            if number==1:compose(project,'build','db','runner')
            compose(project,'up','-d','--wait','--wait-timeout','180','db')
            details=identity(project)
            runner_image=execute(['docker','image','inspect','--format','{{.Id}}','cu-engine-lab-pressure-runner:local'],True)
            raw=compose(project,'run','--rm','--no-deps','-T','runner','python','-m','benchmarks.cache_pressure',
                        '--mode',mode,'--rows',str(item['rows']),'--round',str(item['round']),capture=True)
            # Preserve the worker output before validation, including rejected evidence.
            (directory/f'trial-{number:02d}.json').write_text(raw+'\n',encoding='utf-8')
            trial=json.loads(raw);benchmark.validate_trial(trial,mode,item)
            if any(trial[k]!=v for k,v in expected[item['rows']].items()):raise RuntimeError('Host/worker data mismatch')
            trial.update(position=item['position'],project=project,db_image_id=details['Image'],runner_image_id=runner_image)
            result['trials'].append(trial);save_json(path,result)
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
    p.add_argument('--power-condition',required=True);a=p.parse_args()
    try:run('pilot' if a.pilot else 'full' if a.full else 'smoke',a.power_condition)
    except (Exception,KeyboardInterrupt) as error:
        print('FAILED:',str(error),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
