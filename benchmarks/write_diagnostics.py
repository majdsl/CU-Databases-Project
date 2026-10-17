"""Staged, isolated concurrent writes with SQL lock counters and host CPU samples."""
import argparse
from dataclasses import asdict
import json
import math
import os
import sys
import time

from . import concurrency as writes
from .core import Config, ENGINES, dataset_digest, describe, engine_schedule, generate_rows
from .run import INSERT, ROOT, runtime_metadata, source_fingerprint, variables, verify_rows
from .telemetry import quota_cpus

COUNTERS = ('Table_locks_immediate', 'Table_locks_waited', 'Innodb_row_lock_waits', 'Innodb_row_lock_time')
GAUGES = ('Innodb_row_lock_current_waits',)


def settings(mode):
    if mode not in ('smoke', 'pilot', 'full'):
        raise ValueError('Unknown mode')
    return dict(rows=100 if mode == 'smoke' else 10000,
                updates=100 if mode == 'smoke' else 1000 if mode == 'pilot' else 10000,
                rounds=5 if mode == 'full' else 1)


def schedule(mode):
    cfg = settings(mode)
    conditions = [(m, c) for m in writes.MODES for c in writes.CLIENTS]
    result = []
    for r, order in enumerate(engine_schedule(Config().seed, 5)[:cfg['rounds']], 1):
        rotated = conditions[(r-1) % 6:] + conditions[:(r-1) % 6]
        for engine in order:
            for pattern, clients in rotated:
                result.append(dict(round=r, engine=engine, pattern=pattern, clients=clients))
    return result


def status_snapshot(cursor):
    started = time.perf_counter_ns()
    cursor.execute('SHOW GLOBAL STATUS')
    values = {k.lower(): v for k, v in cursor.fetchall()}
    selected = {}
    for name in COUNTERS + GAUGES:
        value = values.get(name.lower())
        selected[name] = int(value) if value is not None else None
        if selected[name] is not None and selected[name] < 0:
            raise ValueError('Negative status counter')
    return dict(values=selected, sample_duration_seconds=(time.perf_counter_ns()-started)/1e9)


def lock_delta(before, after):
    result = {}
    for name in COUNTERS:
        a, b = before['values'].get(name), after['values'].get(name)
        if a is None or b is None:
            result[name] = None
        elif min(a, b) < 0 or b < a:
            raise ValueError('Status counter reset: '+name)
        else:
            result[name] = b-a
    return result


def server_cpu(before, after):
    if before['container_id'] != after['container_id'] or before['started_at'] != after['started_at']:
        raise ValueError('Database container changed or restarted')
    if before['cpu_max'] != after['cpu_max'] or quota_cpus(before['cpu_max']) != 2:
        raise ValueError('Database CPU quota changed or is not two CPUs')
    for sample in (before, after):
        if sample['call_end_ns'] < sample['call_start_ns']:
            raise ValueError('Invalid sample interval')
    minimum = (after['call_start_ns']-before['call_end_ns'])/1e9
    maximum = (after['call_end_ns']-before['call_start_ns'])/1e9
    if minimum <= 0:
        raise ValueError('Overlapping CPU sample intervals')
    wall = (minimum+maximum)/2
    deltas = {}
    for name in set(before['cpu_stat']) & set(after['cpu_stat']):
        a, b = before['cpu_stat'][name], after['cpu_stat'][name]
        if min(a,b) < 0 or b < a:
            raise ValueError('CPU counter reset')
        deltas[name] = b-a
    if 'usage_usec' not in deltas:
        raise ValueError('CPU usage unavailable')
    seconds = deltas['usage_usec']/1e6
    return dict(before=before, after=after, counter_delta=deltas, cpu_seconds=seconds,
                wall_seconds=wall, wall_seconds_bounds=[minimum,maximum], average_cores=seconds/wall,
                window='write runner startup, connections, SQL observations, writes and teardown; excludes load and verification')


def assert_engine(cursor, engine):
    cursor.execute('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s',
                   ('benchmark_events',))
    row = cursor.fetchone()
    if row is None or row[0].lower() != engine.lower():
        raise RuntimeError('Missing table or engine substitution')


def worker(stage, mode, engine, clients, pattern):
    cfg = settings(mode)
    if os.environ.get('WRITE_DIAGNOSTICS_EXPERIMENT') != 'isolated-v1' or os.environ.get('DB_NAME') != 'engine_lab':
        raise ValueError('Only the isolated diagnostic environment is allowed')
    if engine not in ENGINES or stage not in ('prepare','writes','verify'):
        raise ValueError('Invalid stage or engine')
    keys = writes.streams(cfg['rows'],cfg['updates'],clients,pattern)
    runtime = runtime_metadata()
    if quota_cpus(runtime.get('cgroup_cpu_max','')) != 2:
        raise ValueError('Two-CPU runner required')
    config = Config(rows=cfg['rows'])
    rows = generate_rows(config) if stage != 'writes' else None
    result = dict(stage=stage, mode=mode, engine=engine, clients=clients, pattern=pattern, runtime=runtime)
    with writes.connect() as connection:
        with connection.cursor() as cursor:
            writes.configure(cursor)
            cursor.execute('SELECT VERSION()')
            result['server_version'] = cursor.fetchone()[0]
            if 'MariaDB' not in result['server_version']:
                raise ValueError('MariaDB required')
            if stage == 'prepare':
                cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s',
                               ('benchmark_events',))
                if cursor.fetchone() is not None:
                    raise RuntimeError('Existing table; refusing to overwrite')
                cursor.execute((ROOT/'sql/benchmark'/(engine.lower()+'.sql')).read_text())
                assert_engine(cursor,engine)
                cursor.execute('SHOW CREATE TABLE benchmark_events')
                result['actual_ddl'] = cursor.fetchone()[1]
                for offset in range(0,len(rows),config.batch_size):
                    cursor.executemany(INSERT,rows[offset:offset+config.batch_size])
                result.update(initial_dataset_sha256=verify_rows(cursor,rows),config=asdict(config),
                              global_variables=variables(cursor,'global'),session_variables=variables(cursor,'session'),
                              source_sha256=source_fingerprint())
            elif stage == 'writes':
                assert_engine(cursor,engine)
                before = status_snapshot(cursor)
                start = time.perf_counter_ns()
                result.update(writes.execute_workers(keys))
                elapsed = (time.perf_counter_ns()-start)/1e9
                after = status_snapshot(cursor)
                result.update(lock_before=before,lock_after=after,lock_delta=lock_delta(before,after),
                              lock_window_seconds=elapsed,attempted_updates=cfg['updates'])
                # Return failed worker evidence as JSON; host rejects it before verification/cleanup.
                return result
            else:
                assert_engine(cursor,engine)
                result['verified_final_sha256'] = verify_rows(cursor,writes.expected_rows(rows,keys))
                cursor.execute('DROP TABLE benchmark_events')
    result['status'] = 'completed'
    return result


def validate_trial(trial, mode, expected):
    cfg=settings(mode)
    if any(trial.get(k)!=v for k,v in expected.items()):
        raise ValueError('Trial schedule mismatch')
    for stage in ('prepare','writes','verify'):
        item=trial[stage]
        if item['status']!='completed' or item['stage']!=stage or item['mode']!=mode:
            raise ValueError('Incomplete stage')
        if any(item[k]!=expected[k] for k in ('engine','pattern','clients')):
            raise ValueError('Stage condition mismatch')
    rows=generate_rows(Config(rows=cfg['rows']))
    keys=writes.streams(cfg['rows'],cfg['updates'],expected['clients'],expected['pattern'])
    if trial['prepare']['initial_dataset_sha256']!=dataset_digest(rows):
        raise ValueError('Initial data hash mismatch')
    if trial['verify']['verified_final_sha256']!=dataset_digest(writes.expected_rows(rows,keys)):
        raise ValueError('Final data hash mismatch')
    measured=trial['writes']
    if measured['completed']!=cfg['updates'] or measured['attempted_updates']!=cfg['updates']:
        raise ValueError('Incomplete update count')
    if len(measured['workers'])!=expected['clients']:
        raise ValueError('Missing worker')
    for w in measured['workers']:
        if 'error_type' in w or w['completed']!=cfg['updates']//expected['clients'] or len(w['latency_ms'])!=w['completed']:
            raise ValueError('Incomplete worker')
        describe(w['latency_ms'])
    elapsed=measured['elapsed_seconds']
    if not math.isfinite(elapsed) or elapsed<=0 or not math.isclose(measured['updates_per_second'],cfg['updates']/elapsed):
        raise ValueError('Invalid throughput')
    if measured['lock_delta']!=lock_delta(measured['lock_before'],measured['lock_after']):
        raise ValueError('Lock delta mismatch')
    cpu=trial['db_cpu']
    if cpu!=server_cpu(cpu['before'],cpu['after']):
        raise ValueError('CPU delta mismatch')


def summary(result):
    expected=schedule(result['mode'])
    if result['status']!='completed' or len(result['trials'])!=len(expected):
        raise ValueError('Incomplete run')
    for trial,item in zip(result['trials'],expected):
        validate_trial(trial,result['mode'],item)
    lines=['# Concurrent writes: server CPU and lock counters','',
           'Mode: '+result['mode']+'. Trial means are the statistical units; pilot/smoke are correctness checks only.',
           'DB CPU covers a broader container-launch window than throughput. SQL waits are global counters, not all contention.',
           'InnoDB row waits apply only to InnoDB. n/a denotes missing counters or no sample SD. Cache/durability budgets differ.','',
           '| Engine | Pattern | Clients | Updates/s mean ± SD | DB average cores mean | Table waits mean | InnoDB row waits mean |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    def mean(values):
        return 'n/a' if any(v is None for v in values) else f'{sum(values)/len(values):.3f}'
    for engine in ENGINES:
        for pattern in writes.MODES:
            for clients in writes.CLIENTS:
                trials=[t for t in result['trials'] if (t['engine'],t['pattern'],t['clients'])==(engine,pattern,clients)]
                stats=describe([t['writes']['updates_per_second'] for t in trials])
                sd='n/a' if stats['sample_sd'] is None else f"{stats['sample_sd']:.2f}"
                table=mean([t['writes']['lock_delta']['Table_locks_waited'] for t in trials])
                row=mean([t['writes']['lock_delta']['Innodb_row_lock_waits'] for t in trials]) if engine=='InnoDB' else 'not applicable'
                cores=mean([t['db_cpu']['average_cores'] for t in trials])
                lines.append(f"| {engine} | {pattern} | {clients} | {stats['mean']:.2f} ± {sd} | {cores} | {table} | {row} |")
    return '\n'.join(lines)+'\n'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',required=True,choices=('prepare','writes','verify'))
    p.add_argument('--mode',required=True,choices=('smoke','pilot','full'))
    p.add_argument('--engine',required=True,choices=ENGINES)
    p.add_argument('--clients',required=True,type=int,choices=writes.CLIENTS)
    p.add_argument('--pattern',required=True,choices=writes.MODES)
    a=p.parse_args()
    try: print(json.dumps(worker(a.stage,a.mode,a.engine,a.clients,a.pattern),default=str))
    except Exception as error:
        print('FAILED: '+str(error),file=sys.stderr);return 1
    return 0


if __name__=='__main__':sys.exit(main())
