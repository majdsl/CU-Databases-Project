"""Host-only orchestrator for isolated concurrent-write diagnostics."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import uuid
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks import write_diagnostics as benchmark
from benchmarks.run import save_json

PATTERN=re.compile(r'cu-writes-[0-9a-f]{32}-[0-9]+\Z')


def execute(argv,capture=False):
    r=subprocess.run(argv,cwd=ROOT,check=True,text=True,encoding='utf-8',errors='replace',
                     stdout=subprocess.PIPE if capture else None)
    return r.stdout.strip() if capture else None


def compose(project,*args,capture=False):
    if not PATTERN.fullmatch(project):raise ValueError('Only unique isolated write-diagnostic projects are allowed')
    return execute(['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'compose.write-diagnostics.yaml'),
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
    if len(mounts)!=1 or mounts[0].get('Name')!=project+'_writes_data':
        raise RuntimeError('Unexpected database volume')
    return details


def stop_cleanly(project):
    identity(project)
    compose(project,'stop','-t','120','db')
    state=identity(project)['State']
    if state.get('Status')!='exited' or state.get('ExitCode')!=0 or state.get('OOMKilled'):
        raise RuntimeError('Unclean stop; retain evidence and volume')
    return {k:state.get(k) for k in ('Status','ExitCode','OOMKilled','FinishedAt')}


def cpu_sample(project):
    details=identity(project)
    if details['State']['Status']!='running':raise RuntimeError('Database is not running')
    start=time.perf_counter_ns()
    raw=execute(['docker','exec',details['Id'],'cat','/sys/fs/cgroup/cpu.stat','/sys/fs/cgroup/cpu.max'],True)
    end=time.perf_counter_ns()
    lines=raw.splitlines()
    from benchmarks.telemetry import parse_stat
    return dict(container_id=details['Id'],started_at=details['State']['StartedAt'],
                call_start_ns=start,call_end_ns=end,cpu_stat=parse_stat('\n'.join(lines[:-1])),cpu_max=lines[-1])


def stage(project,directory,number,item,mode,name):
    # Preserve stdout even on failure; never retry an ambiguous update.
    if not PATTERN.fullmatch(project):raise ValueError('Invalid project')
    argv=['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'compose.write-diagnostics.yaml'),
          '-p',project,'run','--rm','--no-deps','-T','runner','python','-m','benchmarks.write_diagnostics',
          '--stage',name,'--mode',mode,'--engine',item['engine'],'--clients',str(item['clients']),
          '--pattern',item['pattern']]
    process=subprocess.run(argv,cwd=ROOT,text=True,encoding='utf-8',errors='replace',stdout=subprocess.PIPE)
    (directory/f'trial-{number:03d}-{name}.json').write_text(process.stdout,encoding='utf-8')
    process.check_returncode()
    return json.loads(process.stdout)


def run(mode,power):
    benchmark.settings(mode)
    if not power.strip():raise ValueError('Record actual power conditions')
    if not (ROOT/'.env').is_file():raise ValueError('Existing .env required; run setup first')
    if execute(['docker','info','--format','{{.OSType}}/{{.Architecture}}'],True) not in ('linux/x86_64','linux/amd64'):
        raise RuntimeError('Linux amd64 Docker engine required')
    token=uuid.uuid4().hex;project=f'cu-writes-{token}-1'
    ensure_new(project)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-write-diagnostics-'+token[:8]
    directory=ROOT/'results'/run_id;directory.mkdir(parents=True,exist_ok=False)
    result=dict(format_version=1,experiment='isolated_write_diagnostics_v1',run_id=run_id,mode=mode,
                power_condition=power,status='running',schedule=benchmark.schedule(mode),trials=[],project=project,
                compose_version=execute(['docker','compose','version','--short'],True),host_python=sys.version,
                source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in
                    ('scripts/run_write_diagnostics.py','compose.write-diagnostics.yaml','benchmarks/write_diagnostics.py')})
    path=directory/'results.json';save_json(path,result)
    try:
        compose(project,'build','db','runner')
        compose(project,'up','-d','--wait','--wait-timeout','180','db')
        details=identity(project);result['db_image_id']=details['Image']
        result['runner_image_id']=execute(['docker','image','inspect','--format','{{.Id}}','cu-engine-lab-writes-runner:local'],True)
        for number,item in enumerate(result['schedule'],1):
            print('Write diagnostics:',item,flush=True)
            trial=dict(item);result['trials'].append(trial);save_json(path,result)
            trial['prepare']=stage(project,directory,number,item,mode,'prepare');save_json(path,result)
            before=cpu_sample(project)
            trial['db_cpu_before']=before
            if before['container_id']!=details['Id'] or before['started_at']!=details['State']['StartedAt']:
                raise RuntimeError('Database replaced or restarted during run')
            trial['writes']=stage(project,directory,number,item,mode,'writes')
            after=cpu_sample(project)
            trial['db_cpu_after']=after;save_json(path,result)
            trial['db_cpu']=benchmark.server_cpu(before,after);save_json(path,result)
            if trial['writes']['status']!='completed':raise RuntimeError('Failed worker; retaining volume')
            trial['verify']=stage(project,directory,number,item,mode,'verify');save_json(path,result)
            benchmark.validate_trial(trial,mode,item)
        result['clean_stop']=stop_cleanly(project)
        result['status']='completed'
        report=benchmark.summary(result)
        compose(project,'down','--volumes','--timeout','120')
        result['cleanup']='completed';save_json(path,result)
        (directory/'summary.md').write_text(report,encoding='utf-8')
        print(report);print('Saved:',directory)
    except BaseException as error:
        result['status']='failed';result['error_type']=type(error).__name__
        try:
            logs=compose(project,'logs','--no-color','--tail','100','db',capture=True)
            (directory/'failure-db.log').write_text(logs+'\n',encoding='utf-8')
            compose(project,'stop','-t','120','db')
        except BaseException:result['stop_on_failure']='failed; inspect isolated project'
        (directory/'summary.md').unlink(missing_ok=True);save_json(path,result)
        print('Partial results:',directory,file=sys.stderr)
        print('Failed isolated project retained:',project,file=sys.stderr)
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
