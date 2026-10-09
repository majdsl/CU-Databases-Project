"""Isolated, post-ack process-crash experiment with a matched clean-restart control."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from benchmarks.core import ENGINES, dataset_digest, engine_schedule
from benchmarks.recovery import make_rows
from benchmarks.run import save_json

PROJECT=re.compile(r'cu-recovery-[0-9a-f]{32}-[0-9]+\Z')


def execute(args, capture=False, timeout=240, combine=False):
    result=subprocess.run(args,cwd=ROOT,check=True,text=True,encoding='utf-8',errors='replace',
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if combine else None,timeout=timeout)
    return result.stdout.strip() if capture else None


def compose(project,*args,capture=False,timeout=240):
    if not PROJECT.fullmatch(project):
        raise ValueError('Refusing a project outside the recovery namespace')
    return execute(['docker','compose','--env-file',str(ROOT/'.env'),'-f',str(ROOT/'compose.recovery.yaml'),
                    '-p',project,*args],capture=capture,timeout=timeout)


def ensure_new(project):
    if not PROJECT.fullmatch(project):
        raise ValueError('Invalid isolated project')
    for resource in ('container','volume','network'):
        ids=execute(['docker',resource,'ls','-q','--filter','label=com.docker.compose.project='+project,
                     *(['-a'] if resource=='container' else [])],capture=True)
        if ids:
            raise RuntimeError('Project already has resources; refusing reuse')
    # Also refuse a same-named unlabelled volume/network or writer container.
    for resource,name in [('volume',project+'_recovery_data'),('network',project+'_default'),('container',project+'-writer')]:
        names=execute(['docker',resource,'ls',*(['-a'] if resource=='container' else []),
                       '--format','{{.Name}}' if resource!='container' else '{{.Names}}'],capture=True)
        if name in names.splitlines():
            raise RuntimeError('An intended resource name already exists')


def inspect(container):
    # Select fields explicitly: never persist Config.Env or credentials.
    format='{{json .State}}\n{{json .Config.Labels}}\n{{json .Mounts}}\n{{json .Image}}'
    lines=execute(['docker','inspect','--format',format,container],capture=True).splitlines()
    if len(lines)!=4:
        raise RuntimeError('Unexpected Docker inspection response')
    return dict(zip(('state','labels','mounts','image_id'),map(json.loads,lines)))


def validate_db(project,info):
    if not PROJECT.fullmatch(project):
        raise ValueError('Invalid isolated project')
    labels=info['labels'] or {}
    if labels.get('com.docker.compose.project')!=project or labels.get('com.docker.compose.service')!='db':
        raise RuntimeError('Container ownership mismatch; refusing operation')
    mounts=info['mounts']
    if len(mounts)!=1 or mounts[0].get('Type')!='volume' or mounts[0].get('Name')!=project+'_recovery_data' or mounts[0].get('Destination')!='/var/lib/mysql':
        raise RuntimeError('Unexpected database mounts; refusing operation')


def get_db(project):
    container=compose(project,'ps','-a','-q','db',capture=True)
    if not re.fullmatch(r'[0-9a-f]{12,64}',container):
        raise RuntimeError('Expected one isolated database container')
    info=inspect(container);validate_db(project,info)
    return container,info


def validate_writer(project,container):
    info=inspect(container)
    labels=info['labels'] or {}
    if labels.get('com.docker.compose.project')!=project or labels.get('com.docker.compose.service')!='runner':
        raise RuntimeError('Writer ownership mismatch')
    return info


def wait_receipt(project,writer,path,timeout=180):
    start=time.monotonic()
    while not path.exists():
        info=validate_writer(project,writer)
        if not info['state']['Running']:
            raise RuntimeError('Writer exited before publishing a complete receipt')
        if time.monotonic()-start>=timeout:
            raise TimeoutError('Writer receipt timed out')
        time.sleep(.1)
    if not validate_writer(project,writer)['state']['Running']:
        raise RuntimeError('Writer is no longer holding its connection open')
    return json.loads(path.read_text(encoding='utf-8'))


def validate_receipt(receipt,engine,rows,seed):
    if (receipt.get('engine'),receipt.get('rows'),receipt.get('seed'))!=(engine,rows,seed):
        raise RuntimeError('Wrong trial receipt')
    if receipt.get('acknowledged_ids')!=list(range(1,rows+1)) or receipt.get('acknowledged_count')!=rows or receipt.get('in_flight_at_receipt')!=0:
        raise RuntimeError('Incomplete acknowledgment ledger')
    if receipt.get('expected_dataset_sha256')!=dataset_digest(make_rows(rows,seed)):
        raise RuntimeError('Host/writer dataset mismatch')


def apply_stop(project,container,mode):
    info=inspect(container);validate_db(project,info)
    if not info['state']['Running']:
        raise RuntimeError('Database stopped before the planned intervention')
    if mode=='sigkill':
        execute(['docker','kill','--signal','KILL',container])
    elif mode=='clean':
        compose(project,'stop','-t','120','db',timeout=150)
    else:
        raise ValueError('Unknown intervention')
    state=inspect(container)['state']
    if state.get('Status')!='exited' or state.get('ExitCode')!=(137 if mode=='sigkill' else 0) or state.get('OOMKilled'):
        raise RuntimeError('Observed stop does not match the planned intervention')
    return {k:state.get(k) for k in ('Status','ExitCode','OOMKilled','FinishedAt')}


def ordinary_outcome(engine,observation):
    if observation.get('status')!='readable':
        return False
    if observation.get('check_table_error_code') is not None or any(str(row[2]).lower()=='error' for row in observation.get('check_table_messages', [])):
        return False
    if observation['exact_match']:
        return True
    return (engine=='MEMORY' and observation['observed_rows']==0 and
            len(observation['missing_ids'])==observation['expected_rows'] and
            not any(observation[k] for k in ('changed_ids','unexpected_ids','duplicate_ids')))


def markdown(result):
    if result['status']!='completed':
        raise ValueError('Incomplete protocol cannot have a success report')
    expected={(r,e,m) for r in range(1,result['rounds']+1) for e in ENGINES for m in ('clean','sigkill')}
    if len(result['trials'])!=len(expected) or {(t['round'],t['engine'],t['mode']) for t in result['trials']}!=expected:
        raise ValueError('Missing or duplicate conditions')
    lines=['# Recovery '+('pilot' if result['pilot'] else 'experiment'),'','Run: '+result['run_id'],'',
        f"{result['rows']} acknowledged single-row autocommit inserts per trial; {result['rounds']} round(s).",
        'Each trial uses a fresh volume. No write is in flight at the planned stop.',
        'SIGKILL tests a database-process crash with host/kernel still running, not power loss.','',
        '| Engine | Round | Stop | Observation | Intact rows | Missing | Changed | Restart through verification (s) |',
        '| --- | --- | --- | --- | ---: | ---: | ---: | ---: |']
    for t in result['trials']:
        o=t['observation'];readable=o['status']=='readable'
        lines.append(f"| {t['engine']} | {t['round']} | {t['mode']} | {o['status']} | "
            f"{o['intact_rows'] if readable else 'n/a'} | {len(o['missing_ids']) if readable else 'n/a'} | "
            f"{len(o['changed_ids']) if readable else 'n/a'} | {t['restart_through_verification_seconds']:.3f} |")
    lines+=['','Timing includes Docker startup, observer-container launch, connection polling, full data read and CHECK TABLE.',
        'It is not engine-only recovery latency. Unavailable/unreadable tables have unknown survival, not zero rows.',
        'MEMORY rows are volatile even for clean restarts. Data survival in this test is not a durability guarantee.',
        'The writer holds its connection open until the stop; receipt transfer and host orchestration introduce delay.',
        'Automatic engine recovery may occur; the harness never issues REPAIR TABLE or forces compaction.',
        'Completed means the protocol finished, not that every engine preserved every row.',
        'Raw receipts, observations, source hashes, settings, timings and server logs are saved beside this report.',
        'Retained projects needing review: '+str(len(result['retained_projects'])),
        'See docs/recovery-method.md for protocol and limitations.','']
    return '\n'.join(lines)


def run(args):
    make_rows(args.rows,args.seed)
    if not (ROOT/'.env').is_file():
        raise ValueError('Existing project .env required; do not upload it')
    if execute(['docker','info','--format','{{.OSType}}'],capture=True)!='linux':
        raise RuntimeError('Linux containers required')
    token=uuid.uuid4().hex
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-recovery-'+token[:8]
    directory=ROOT/'results'/run_id;directory.mkdir(parents=True,exist_ok=False)
    schedule=engine_schedule(args.seed,5)[:1 if args.pilot else 5]
    sources=['compose.recovery.yaml','Dockerfile','scripts/run_recovery.py','benchmarks/recovery.py']
    result=dict(format_version=1,experiment='post_ack_process_recovery',status='running',run_id=run_id,
        pilot=args.pilot,rounds=len(schedule),rows=args.rows,seed=args.seed,schedule=schedule,
        power_condition=args.power_condition,host_platform=platform.platform(),host_python=sys.version,
        compose_version=execute(['docker','compose','version','--short'],capture=True),
        source_sha256={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sources},
        trials=[],retained_projects=[])
    current=None;writer=None;db=None
    def checkpoint(): save_json(directory/'results.json',result)
    checkpoint()
    try:
        for round_number,engines in enumerate(schedule,1):
            for position,engine in enumerate(engines):
                modes=('clean','sigkill') if (round_number+position)%2 else ('sigkill','clean')
                for mode in modes:
                    project=f'cu-recovery-{token}-{len(result["trials"])+1}'
                    ensure_new(project);current=project;writer=None;db=None
                    result['active_project']=project;checkpoint()
                    trial_dir=directory/f'{len(result["trials"])+1:02d}-{engine.lower()}-{mode}'
                    trial_dir.mkdir()
                    print(f'Recovery round {round_number}/{len(schedule)}: {engine} {mode}',flush=True)
                    if not result['trials']:
                        compose(project,'build','db','runner',timeout=900)
                    compose(project,'up','-d','--wait','--wait-timeout','180','db')
                    db,info=get_db(project)
                    if execute(['docker','exec',db,'cat','/proc/1/comm'],capture=True) not in ('mariadbd','mysqld'):
                        raise RuntimeError('PID 1 is not the database server; crash target is invalid')
                    trial=dict(engine=engine,mode=mode,round=round_number,project=project,db_image_id=info['image_id'])
                    receipt_path=trial_dir/'acknowledgments.json'
                    container_receipt='/results/'+run_id+'/'+trial_dir.name+'/acknowledgments.json'
                    writer=compose(project,'run','-d','--no-deps','--name',project+'-writer','runner',
                        'python','-m','benchmarks.recovery','prepare','--engine',engine,'--rows',str(args.rows),
                        '--seed',str(args.seed),'--receipt',container_receipt,capture=True)
                    if not re.fullmatch(r'[0-9a-f]{12,64}',writer):
                        raise RuntimeError('Unexpected writer container ID')
                    receipt=wait_receipt(project,writer,receipt_path)
                    seen=time.monotonic();validate_receipt(receipt,engine,args.rows,args.seed)
                    trial['acknowledgments']=receipt
                    trial['runner_image_id']=validate_writer(project,writer)['image_id']
                    result['active_trial']=trial;checkpoint()
                    trial['receipt_seen_to_stop_request_seconds']=time.monotonic()-seen
                    trial['stop_requested_utc']=datetime.now(timezone.utc).isoformat()
                    trial['stopped_state']=apply_stop(project,db,mode)
                    checkpoint()
                    validate_writer(project,writer)
                    execute(['docker','rm','-f',writer]);writer=None
                    restarted=datetime.now(timezone.utc).isoformat();start=time.monotonic()
                    # Start only this existing container, never create a fresh DB on restart.
                    validate_db(project,inspect(db));execute(['docker','start',db])
                    observation=json.loads(compose(project,'run','--rm','--no-deps','-T','runner',
                        'python','-m','benchmarks.recovery','observe','--rows',str(args.rows),'--seed',str(args.seed),
                        '--timeout','120',capture=True,timeout=160))
                    trial['restart_through_verification_seconds']=time.monotonic()-start
                    trial['restart_requested_utc']=restarted;trial['observation']=observation
                    logs=execute(['docker','logs','--since',restarted,db],capture=True,combine=True)
                    (trial_dir/'restart.log').write_text(logs+'\n',encoding='utf-8')
                    trial['restart_log']=str((trial_dir/'restart.log').relative_to(directory))
                    trial['restart_log_sha256']=hashlib.sha256((trial_dir/'restart.log').read_bytes()).hexdigest()
                    trial['post_observation_state']=inspect(db)['state']
                    trial['cleanup']='pending';result['trials'].append(trial);checkpoint()
                    validate_db(project,inspect(db))
                    if ordinary_outcome(engine,observation):
                        compose(project,'down','--volumes','--timeout','120',timeout=150)
                        trial['cleanup']='removed_own_disposable_resources'
                    else:
                        compose(project,'stop','-t','120','db',timeout=150)
                        trial['cleanup']='retained_for_review';result['retained_projects'].append(project)
                    current=None;db=None;result.pop('active_project',None);result.pop('active_trial',None);checkpoint()
        result['status']='completed';summary=markdown(result)
        (directory/'summary.md').write_text(summary,encoding='utf-8');checkpoint()
        print(summary);print('Saved:',directory)
    except BaseException as error:
        result['status']='failed';result['error_type']=type(error).__name__
        # Preserve partial receipts and volumes; stop only containers verified as ours.
        if writer:
            try:
                validate_writer(current,writer)
                logs=execute(['docker','logs',writer],capture=True,combine=True)
                (directory/'writer-failure.log').write_text(logs+'\n',encoding='utf-8')
                execute(['docker','rm','-f',writer])
            except (Exception,KeyboardInterrupt): result['writer_cleanup']='needs_review'
        if current and db is None:
            try: db,_=get_db(current)
            except (Exception,KeyboardInterrupt): result['db_stop_on_failure']='needs_review'
        if db:
            try:
                validate_db(current,inspect(db));compose(current,'stop','-t','120','db',timeout=150)
            except (Exception,KeyboardInterrupt): result['db_stop_on_failure']='needs_review'
        (directory/'summary.md').unlink(missing_ok=True);checkpoint()
        print('Partial results:',directory,file=sys.stderr)
        raise


def main():
    p=argparse.ArgumentParser(description=__doc__)
    mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pilot',action='store_true',help='One clean and one forced restart per engine (10 trials)')
    mode.add_argument('--full',action='store_true',help='Five rounds per engine/stop condition (50 trials)')
    p.add_argument('--rows',type=int,default=1000);p.add_argument('--seed',type=int,default=20260923)
    p.add_argument('--power-condition',default='not recorded');args=p.parse_args()
    try: run(args)
    except (Exception,KeyboardInterrupt) as error:
        print('FAILED:',str(error),file=sys.stderr);return 1
    return 0

if __name__=='__main__':
    sys.exit(main())
