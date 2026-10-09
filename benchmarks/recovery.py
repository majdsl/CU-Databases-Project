"""Controlled post-acknowledgment restart test; used by the isolated host driver."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time

from .core import Config, ENGINES, dataset_digest, generate_rows, row_bytes
from .run import INSERT, SELECT_ALL, LOCK_NAME, ROOT, VARIABLES, runtime_metadata, source_fingerprint


def guard():
    if os.environ.get('RECOVERY_EXPERIMENT') != 'isolated-process-v1' or os.environ.get('DB_NAME') != 'engine_lab':
        raise ValueError('Use scripts/run_recovery.py with the isolated Compose file')


def make_rows(count, seed):
    if type(count) is not int or not 100 <= count <= 10000:
        raise ValueError('Recovery rows must be 100..10000')
    return generate_rows(Config(rows=count, seed=seed))


def connect():
    import pymysql
    return pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
        password=os.environ['DB_PASSWORD'], database='engine_lab', charset='utf8mb4',
        autocommit=True, connect_timeout=2, read_timeout=10, write_timeout=30)


def save_receipt(path, result):
    """Flush the complete acknowledgment record before signaling readiness by rename."""
    path = Path(path)
    if path.exists():
        raise RuntimeError('Receipt already exists; refusing reuse')
    temporary = path.with_suffix('.tmp')
    with temporary.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2, default=str)
        stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)


def insert_acknowledged(cursor, rows):
    acknowledged = []
    for row in rows:
        cursor.execute(INSERT, row)
        if cursor.rowcount != 1:
            raise RuntimeError('Insert did not affect exactly one row')
        acknowledged.append(row[0])
    return acknowledged


def prepare(engine, count, seed, receipt):
    guard()
    if engine not in ENGINES:
        raise ValueError('Unknown engine')
    rows = make_rows(count, seed)
    with connect() as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT GET_LOCK(%s, 0)', (LOCK_NAME,))
            if cursor.fetchone()[0] != 1:
                raise RuntimeError('Another experiment owns the database lock')
            cursor.execute('SHOW TABLES')
            if cursor.fetchall():
                raise RuntimeError('Refusing a nonempty engine_lab database')
            cursor.execute("SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
            cursor.execute('SET SESSION query_cache_type = OFF')
            cursor.execute('SET SESSION max_heap_table_size = 134217728')
            cursor.execute('SELECT VERSION()')
            version = cursor.fetchone()[0]
            if 'MariaDB' not in version:
                raise RuntimeError('MariaDB required')
            cursor.execute((ROOT/'sql/benchmark'/(engine.lower()+'.sql')).read_text())
            cursor.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='benchmark_events'")
            if cursor.fetchone()[0].lower() != engine.lower():
                raise RuntimeError('Engine substitution detected')
            cursor.execute('SHOW CREATE TABLE benchmark_events')
            ddl = cursor.fetchone()[1]
            metadata = {}
            names = VARIABLES | {'myisam_recover_options', 'innodb_fast_shutdown', 'innodb_doublewrite'}
            for scope in ('GLOBAL', 'SESSION'):
                cursor.execute('SHOW '+scope+' VARIABLES')
                metadata[scope.lower()+'_variables'] = {k:v for k,v in cursor.fetchall() if k.lower() in names}
            result = dict(engine=engine, rows=count, seed=seed, server_version=version,
                actual_ddl=ddl, expected_dataset_sha256=dataset_digest(rows),
                source_sha256=source_fingerprint(), runtime=runtime_metadata(), **metadata)
            # No ANALYZE, row validation, CHECK TABLE, FLUSH or connection close after these writes.
            result['acknowledged_ids'] = insert_acknowledged(cursor, rows)
            result['acknowledged_count'] = len(result['acknowledged_ids'])
            result['last_ack_observed_utc'] = datetime.now(timezone.utc).isoformat()
            result['in_flight_at_receipt'] = 0
            save_receipt(receipt, result)
            # Host applies the stop while this connection and advisory lock remain open.
            # It removes this disposable writer container only after the DB has stopped.
            while True:
                time.sleep(1)


def compare_rows(expected, actual):
    """Do not confuse an unreadable table with an empty one; call only after a full read."""
    want = {row[0]:tuple(row) for row in expected}
    seen, unchanged, changed, unexpected, duplicates = set(), [], [], [], []
    digest = hashlib.sha256()
    for row in actual:
        row=tuple(row); digest.update(row_bytes(row)); key=row[0]
        if key in seen:
            duplicates.append(key)
        seen.add(key)
        if key not in want:
            unexpected.append(key)
        elif row != want[key]:
            changed.append(key)
        else:
            unchanged.append(key)
    missing=sorted(set(want)-seen)
    return dict(status='readable', expected_rows=len(expected), observed_rows=len(actual),
        intact_rows=len(unchanged), missing_ids=missing, changed_ids=changed,
        unexpected_ids=unexpected, duplicate_ids=duplicates,
        actual_dataset_sha256=digest.hexdigest(), expected_dataset_sha256=dataset_digest(expected),
        exact_match=not (missing or changed or unexpected or duplicates) and len(actual)==len(expected))


def error_code(error):
    return error.args[0] if error.args and type(error.args[0]) is int else None


def observe(count, seed, timeout):
    guard(); expected=make_rows(count,seed)
    import pymysql
    start=time.monotonic(); attempts=0; last=None
    # Only connection/readiness failures are retried. Never retry a data read or a write.
    while True:
        connection=None; attempts+=1
        try:
            connection=connect()
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1'); cursor.fetchone()
            break
        except pymysql.MySQLError as error:
            last=error_code(error)
            if connection is not None:
                connection.close()
            if last not in (2002,2003,2006,2013) or time.monotonic()-start >= timeout:
                return dict(status='unavailable', error_code=last, attempts=attempts,
                            observer_wait_seconds=time.monotonic()-start)
            time.sleep(.25)
    ready=time.monotonic()-start
    try:
        with connection.cursor() as cursor:
            try:
                cursor.execute(SELECT_ALL)
                result=compare_rows(expected,cursor.fetchall())
            except pymysql.MySQLError as error:
                result=dict(status='unreadable',error_code=error_code(error))
            # Diagnostic AFTER the observation; no REPAIR TABLE is issued.
            try:
                cursor.execute('CHECK TABLE benchmark_events')
                result['check_table_messages']=cursor.fetchall()
            except pymysql.MySQLError as error:
                result['check_table_error_code']=error_code(error)
        result.update(attempts=attempts, observer_wait_seconds=ready)
        return result
    finally:
        connection.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--engine',choices=ENGINES,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    q=sub.add_parser('observe');q.add_argument('--timeout',type=int,default=120)
    for part in (p,q):
        part.add_argument('--rows',type=int,default=1000);part.add_argument('--seed',type=int,default=20260923)
    args=parser.parse_args()
    if args.action=='prepare':
        prepare(args.engine,args.rows,args.seed,args.receipt)
    else:
        if not 1 <= args.timeout <= 120:
            raise ValueError('Readiness timeout must be 1..120 seconds')
        print(json.dumps(observe(args.rows,args.seed,args.timeout),default=str))

if __name__=='__main__':
    main()
