"""One isolated InnoDB cache-pressure trial; streamed data, verified reads."""
import argparse
import hashlib
import json
import os
import random
import statistics
import sys
import time
import zlib

from .core import describe
from .run import LOCK_NAME, runtime_metadata, source_fingerprint, variables

POOL = 134217728
PAYLOAD = 1024
SEED = 20261017
COUNTERS = ('Innodb_buffer_pool_reads', 'Innodb_buffer_pool_read_requests',
            'Innodb_buffer_pool_read_ahead', 'Innodb_buffer_pool_wait_free',
            'Innodb_data_reads', 'Innodb_data_read')
GAUGES = ('Innodb_buffer_pool_pages_data', 'Innodb_buffer_pool_pages_dirty',
          'Innodb_buffer_pool_pages_free')
DDL = ('CREATE TABLE cache_pressure_rows (id INT NOT NULL PRIMARY KEY, '
       'payload VARBINARY(1024) NOT NULL) ENGINE=InnoDB ROW_FORMAT=DYNAMIC')
POINT = 'SELECT payload FROM cache_pressure_rows WHERE id=%s'
SCAN = 'SELECT COUNT(*), COALESCE(SUM(CRC32(payload)),0) FROM cache_pressure_rows'


def settings(mode):
    if mode not in ('pilot', 'full', 'smoke'):
        raise ValueError('Unknown mode')
    return dict(sizes=[128,1024] if mode=='smoke' else [32768,262144],
                rounds=6 if mode=='full' else 1,
                queries=30 if mode=='smoke' else 1000 if mode=='pilot' else 5000,
                warmup=10 if mode=='smoke' else 1000, scans=2 if mode=='smoke' else 3)


def schedule(mode):
    c=settings(mode)
    return [dict(round=r+1,rows=n,position=p+1) for r in range(c['rounds'])
            for p,n in enumerate(c['sizes'] if r%2==0 else c['sizes'][::-1])]


def payload(key):
    return hashlib.shake_256(f'{SEED}:{key}'.encode()).digest(PAYLOAD)


def keys(rows, round_number, count, warm=False):
    rng=random.Random(SEED+round_number*1000003+(71 if warm else 0))
    return [rng.randint(1,rows) for _ in range(count)]


def digest_update(digest, key, value):
    digest.update(key.to_bytes(8,'big'));digest.update(value)


def snapshot(cursor):
    cursor.execute('SHOW GLOBAL STATUS')
    all_status=dict(cursor.fetchall())
    missing=set(COUNTERS+GAUGES)-all_status.keys()
    if missing:raise RuntimeError('Missing counters: '+','.join(sorted(missing)))
    return {k:int(all_status[k]) for k in COUNTERS+GAUGES}


def delta(before, after):
    if any(after[k]<before[k] for k in COUNTERS):
        raise RuntimeError('Counter reset; refusing invalid delta')
    return {k:after[k]-before[k] for k in COUNTERS}


def check_footprint(mode, rows, allocated, pool):
    if pool!=POOL:raise RuntimeError('Buffer pool differs from fixed 128 MiB')
    if allocated<=0:raise RuntimeError('Missing table allocation')
    if mode!='smoke':
        if rows==32768 and allocated>=pool:raise RuntimeError('Small table does not fit the pool')
        if rows==262144 and (rows*PAYLOAD<2*pool or allocated<=pool):
            raise RuntimeError('Large table not proven larger than the pool')


def verify_stream(cursor, rows, expected_hash):
    digest=hashlib.sha256();count=0;crc_sum=0
    cursor.execute('SELECT id,payload FROM cache_pressure_rows ORDER BY id')
    while batch:=cursor.fetchmany(500):
        for key,value in batch:
            count+=1
            if key!=count or value!=payload(count):raise RuntimeError('Loaded data mismatch')
            digest_update(digest,key,value);crc_sum+=zlib.crc32(value)
    if count!=rows or digest.hexdigest()!=expected_hash:raise RuntimeError('Missing rows or bad digest')
    return crc_sum


def query(cursor, statement, params, expected):
    started=time.perf_counter_ns();cursor.execute(statement,params);actual=cursor.fetchone()
    elapsed=(time.perf_counter_ns()-started)/1e6
    if actual is None or tuple(actual)!=tuple(expected):raise RuntimeError('Read answer mismatch')
    return elapsed


def one_trial(mode, rows, round_number):
    c=settings(mode)
    if rows not in c['sizes'] or not 1<=round_number<=c['rounds']:raise ValueError('Invalid trial')
    if os.environ.get('CACHE_PRESSURE_EXPERIMENT')!='isolated-v1' or os.environ.get('DB_NAME')!='engine_lab':
        raise ValueError('Use the isolated host orchestrator')
    import pymysql
    result=dict(mode=mode,rows=rows,round=round_number,seed=SEED,payload_bytes=PAYLOAD,
                payload_total_bytes=rows*PAYLOAD,runtime=runtime_metadata(),source_sha256=source_fingerprint())
    with pymysql.connect(host=os.environ['DB_HOST'],user=os.environ['DB_USER'],password=os.environ['DB_PASSWORD'],
            database='engine_lab',autocommit=True,connect_timeout=10,read_timeout=600,write_timeout=600) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT GET_LOCK(%s,0)',(LOCK_NAME,))
            if cursor.fetchone()[0]!=1:raise RuntimeError('Database busy')
            cursor.execute('SELECT VERSION()');result['server_version']=cursor.fetchone()[0]
            if 'MariaDB' not in result['server_version']:raise RuntimeError('MariaDB required')
            cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',('cache_pressure_rows',))
            if cursor.fetchone() is not None:raise RuntimeError('Existing table; refusing modification')
            cursor.execute("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
            cursor.execute('SET SESSION query_cache_type=OFF')
            cursor.execute('SELECT @@innodb_buffer_pool_size,@@innodb_page_size')
            pool,page_size=cursor.fetchone()
            if pool!=POOL:raise RuntimeError('Wrong buffer-pool size')
            result['buffer_pool_bytes']=pool;result['innodb_page_size']=page_size
            result['global_variables']=variables(cursor,'global');result['session_variables']=variables(cursor,'session')
            cursor.execute('SHOW GLOBAL VARIABLES')
            result['innodb_settings']={k:v for k,v in cursor.fetchall() if k.startswith('innodb_')}
            cursor.execute(DDL)
            cursor.execute('SHOW CREATE TABLE cache_pressure_rows');result['actual_ddl']=cursor.fetchone()[1]
            cursor.execute('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s',('cache_pressure_rows',))
            if cursor.fetchone()[0].upper()!='INNODB':raise RuntimeError('Engine substitution')
            digest=hashlib.sha256();started=time.perf_counter()
            for start in range(1,rows+1,500):
                batch=[(i,payload(i)) for i in range(start,min(start+500,rows+1))]
                for i,v in batch:digest_update(digest,i,v)
                cursor.executemany('INSERT INTO cache_pressure_rows (id,payload) VALUES (%s,%s)',batch)
            result['load_with_generation_seconds']=time.perf_counter()-started
            result['dataset_sha256']=digest.hexdigest()
        # Unbuffered cursor prevents a 256 MiB result set from filling runner memory.
        with connection.cursor(pymysql.cursors.SSCursor) as stream:
            crc_sum=verify_stream(stream,rows,result['dataset_sha256'])
        result['verified_rows']=rows;result['crc32_sum']=crc_sum
        with connection.cursor() as cursor:
            cursor.execute('ANALYZE TABLE cache_pressure_rows');result['analyze_messages']=cursor.fetchall()
            if not result['analyze_messages'] or not all(r[2:] == ('status','OK') for r in result['analyze_messages']):
                raise RuntimeError('ANALYZE did not succeed')
            cursor.execute("SHOW TABLE STATUS WHERE Name='cache_pressure_rows'")
            status=dict(zip([d[0] for d in cursor.description],cursor.fetchone()))
            result['engine_reported_table_status']=status
            allocated=int(status['Data_length'])+int(status['Index_length'])
            result['engine_reported_bytes']=allocated
            check_footprint(mode,rows,allocated,pool)
            warm=keys(rows,round_number,c['warmup'],True)
            measured=keys(rows,round_number,c['queries'])
            result['warmup_ids']=warm;result['lookup_ids']=measured
            for key in warm:query(cursor,POINT,(key,),(payload(key),))
            before=snapshot(cursor)
            result['lookup_ms']=[query(cursor,POINT,(key,),(payload(key),)) for key in measured]
            after=snapshot(cursor)
            result['lookup_counters']=dict(before=before,after=after,delta=delta(before,after))
            result['scan_ms']=[];result['scan_counters']=[]
            for _ in range(c['scans']):
                before=snapshot(cursor);result['scan_ms'].append(query(cursor,SCAN,None,(rows,crc_sum)))
                after=snapshot(cursor);result['scan_counters'].append(dict(before=before,after=after,delta=delta(before,after)))
            result['plans']={}
            for label,sql,params in [('lookup',POINT,(measured[0],)),('scan',SCAN,None)]:
                cursor.execute('EXPLAIN '+sql,params)
                names=[d[0] for d in cursor.description];result['plans'][label]=[dict(zip(names,r)) for r in cursor.fetchall()]
            cursor.execute('SELECT @@innodb_buffer_pool_size');result['buffer_pool_after_bytes']=cursor.fetchone()[0]
            if result['buffer_pool_after_bytes']!=pool:raise RuntimeError('Pool changed during trial')
    # Host retains this table until successful validation and cleanup of its isolated project.
    return result


def validate_trial(t, mode, item):
    c=settings(mode)
    if any(t[k]!=item[k] for k in ('rows','round')) or t['mode']!=mode:raise ValueError('Trial identity differs')
    if t['verified_rows']!=t['rows'] or len(t['lookup_ms'])!=c['queries'] or len(t['scan_ms'])!=c['scans']:
        raise ValueError('Incomplete trial')
    if t['seed']!=SEED or t['payload_bytes']!=PAYLOAD or t['payload_total_bytes']!=t['rows']*PAYLOAD:
        raise ValueError('Wrong dataset configuration')
    if t['lookup_ids']!=keys(t['rows'],t['round'],c['queries']) or t['warmup_ids']!=keys(t['rows'],t['round'],c['warmup'],True):
        raise ValueError('Wrong query streams')
    if t['buffer_pool_after_bytes']!=POOL:raise ValueError('Pool changed')
    check_footprint(mode,t['rows'],t['engine_reported_bytes'],t['buffer_pool_bytes'])
    for values in (t['lookup_ms'],t['scan_ms']):describe(values)
    if len(t['scan_counters'])!=c['scans']:raise ValueError('Missing scan counters')
    for group in [t['lookup_counters']]+t['scan_counters']:
        if group['delta']!=delta(group['before'],group['after']):raise ValueError('Bad counter deltas')
    if t['plans']['lookup'][0]['key']!='PRIMARY':raise ValueError('Point lookup not using primary key')


def summary(result):
    mode=result['mode'];expected=schedule(mode)
    if result['status']!='completed' or result['schedule']!=expected or len(result['trials'])!=len(expected):
        raise ValueError('Incomplete run')
    stats={}
    for t,item in zip(result['trials'],expected):
        if t['position']!=item['position']:raise ValueError('Wrong trial position')
        validate_trial(t,mode,item)
        if any(t[k]!=v for k,v in result['expected_data'][str(t['rows'])].items()):
            raise ValueError('Host oracle mismatch')
        stop=t.get('clean_stop',{})
        if stop.get('Status')!='exited' or stop.get('ExitCode')!=0 or stop.get('OOMKilled'):
            raise ValueError('No verified clean stop')
    for n in settings(mode)['sizes']:
        trials=[t for t in result['trials'] if t['rows']==n]
        if len({t['dataset_sha256'] for t in trials})!=1:raise ValueError('Datasets differ across rounds')
        stats[str(n)]={field:describe([statistics.mean(t[field]) for t in trials]) for field in ('lookup_ms','scan_ms')}
    return stats


def markdown(result):
    stats=summary(result)
    lines=['# InnoDB cache-pressure '+result['mode'],'','Run: '+result['run_id'],
           'Fixed 128 MiB buffer pool; post-verification random lookups then full scans.',
           'Mean ± sample SD of trial means, in milliseconds. Pilot/smoke: no performance conclusion.','',
           '| Rows | Payload MiB | Lookup ms | Scan ms |','| ---: | ---: | ---: | ---: |']
    for n,metrics in stats.items():
        cells=[]
        for s in metrics.values():
            cells.append(f"{s['mean']:.4f} ± "+('n/a' if s['sample_sd'] is None else f"{s['sample_sd']:.4f}"))
        lines.append('| '+' | '.join([n,f'{int(n)*PAYLOAD/1048576:.3f}']+cells)+' |')
    lines+=['','Inspect per-phase InnoDB counters and actual table bytes in results.json.',
            'Buffer-pool misses are not proof of physical SSD reads: OS/virtualization caches remain.',
            'One engine; not a five-engine ranking, equal-budget comparison or isolated server CPU time.',
            'CRC32 scan includes checksum computation; load includes payload generation. See docs/cache-pressure-method.md.','']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--mode',choices=('pilot','full','smoke'),required=True)
    p.add_argument('--rows',type=int,required=True);p.add_argument('--round',type=int,required=True)
    a=p.parse_args();print(json.dumps(one_trial(a.mode,a.rows,a.round),default=str))


if __name__=='__main__':main()
