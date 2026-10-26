"""Exercise tutorial SQL only on a verified disposable GitHub CI database."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
PROJECT = re.compile(r'cu-ci-[0-9]+-[0-9]+\Z')
ENGINES = ('innodb', 'aria', 'myisam', 'memory', 'rocksdb')
FILES = ('01-create-tables.sql', '02-myrocks.sql', '03-compare.sql', '03b-myrocks-compare.sql',
         '04-index-types.sql', '05-lock-demo.sql', '06-after-restart.sql',
         '06b-myrocks-after-restart.sql', '99-cleanup.sql')
CLIENT = 'export MYSQL_PWD="$MARIADB_PASSWORD"; exec mariadb --abort-source-on-error --batch --raw --skip-column-names -ubenchmark engine_lab'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def validate_project(project):
    if not PROJECT.fullmatch(project):
        raise ValueError('Tutorial driver accepts only disposable cu-ci-<run>-<attempt> projects')


def command(argv, input_text=None):
    result = subprocess.run(argv, cwd=ROOT, input=input_text, text=True, encoding='utf-8',
                            errors='replace', capture_output=True, timeout=180)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or 'Tutorial command failed')
    return result.stdout.strip()


def compose(project, *args, input_text=None):
    validate_project(project)
    return command(['docker', 'compose', '--env-file', str(ROOT/'.env'), '-f', str(ROOT/'compose.yaml'),
                    '-p', project, *args], input_text)


def identity(project):
    container = compose(project, 'ps', '-a', '-q', 'db')
    require(bool(container) and len(container.splitlines()) == 1, 'Expected one CI database')
    info = json.loads(command(['docker', 'inspect', container]))[0]
    labels = info['Config']['Labels']
    mounts = [m for m in info['Mounts'] if m['Destination'] == '/var/lib/mysql']
    require(labels.get('com.docker.compose.project') == project and
            labels.get('com.docker.compose.service') == 'db', 'Database labels do not match CI project')
    require(len(mounts) == 1 and mounts[0].get('Name') == project+'_db_data', 'Unexpected database volume')
    require(info['State']['Status'] == 'running' and not info['State'].get('OOMKilled'), 'Database is not running normally')
    return info['Id']


def sql(project, text):
    return compose(project, 'exec', '-T', 'db', 'sh', '-c', CLIENT, input_text=text+'\n')


def source(project, name):
    require(name in FILES, 'Unexpected tutorial source path')
    output = sql(project, 'source /tutorial/'+name)
    print('SQL PASS:', name, flush=True)
    return output


def table_summary(project, engine):
    require(engine in ENGINES, 'Unknown engine')
    # Identifiers come only from the fixed engine whitelist, never from user input.
    out = sql(project, 'SELECT COUNT(*), SUM(id), SUM(airport_id), SUM(delay_min), SUM(hits), '
              "SUM(note <> CONCAT('row-', id)) FROM tut_"+engine+';')
    return [int(v) for v in out.split('\t')]


def hammer(project, engine, row_id, seconds=1):
    require(engine in ENGINES and row_id in (1, 2), 'Unexpected tutorial writer')
    out = sql(project, "CALL tut_hammer('"+engine+"', "+str(row_id)+', '+str(seconds)+');')
    cells = out.split('\t')
    require(len(cells) == 5 and cells[0] == engine and int(cells[1]) == row_id, 'Unexpected writer result')
    require(int(cells[2]) > 0 and float(cells[3]) > 0, 'No successful tutorial updates')
    return dict(engine=engine, row_id=row_id, updates=int(cells[2]), elapsed_seconds=float(cells[3]))


def check_invalid_inputs(project):
    calls = ("CALL tut_hammer('innodb', 1, NULL);", "CALL tut_hammer('innodb', 1, 0);",
             "CALL tut_hammer(NULL, 1, 1);", "CALL tut_hammer('unknown', 1, 1);",
             "CALL tut_hammer('innodb', NULL, 1);", "CALL tut_hammer('innodb', 999999, 1);")
    for text in calls:
        try:
            sql(project, text)
        except RuntimeError as error:
            require('45000' in str(error), 'Expected a routine validation failure')
        else:
            raise RuntimeError('Invalid routine call was accepted')
    require(table_summary(project, 'innodb')[4] == 0, 'Rejected calls changed the data')
    return len(calls)


def check_indexes(project):
    checks = []
    for index in ('btree', 'hash'):
        table = 'tut_idx_'+index
        actual = sql(project, "SELECT INDEX_TYPE FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='"+table+"' AND INDEX_NAME='by_airport';")
        require(actual == index.upper(), 'Unexpected MEMORY index type')
        for predicate, expected, access in (('airport_id = 100', 20, 'ref'),
                                             ('airport_id BETWEEN 100 AND 109', 200, 'range' if index == 'btree' else 'ALL')):
            require(int(sql(project, 'SELECT COUNT(*) FROM '+table+' WHERE '+predicate+';')) == expected, 'Wrong index-query answer')
            plan = sql(project, 'EXPLAIN SELECT COUNT(*) FROM '+table+' WHERE '+predicate+';').split('\t')
            require(len(plan) >= 6 and plan[3] == access, 'Unexpected index access path')
            checks.append(dict(index=index, predicate=predicate, count=expected, access=plan[3], key=plan[5]))
    return checks


def concurrent_writes(project, engine, same_row):
    ids = (1, 1) if same_row else (1, 2)
    before = {row: int(sql(project, 'SELECT hits FROM tut_'+engine+' WHERE id='+str(row)+';')) for row in set(ids)}
    barrier = threading.Barrier(2)
    def work(row):
        barrier.wait(timeout=30)
        return hammer(project, engine, row)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(work, row) for row in ids]
        writers = [f.result() for f in futures]
    for row in set(ids):
        actual = int(sql(project, 'SELECT hits FROM tut_'+engine+' WHERE id='+str(row)+';'))
        require(actual == before[row]+sum(w['updates'] for w in writers if w['row_id'] == row), 'Concurrent increments were lost or miscounted')
    return dict(engine=engine, pattern='same row' if same_row else 'disjoint', writers=writers)


def run_sequence(project, rocks):
    engines = ENGINES if rocks else ENGINES[:-1]
    source(project, '01-create-tables.sql')
    if rocks:
        source(project, '02-myrocks.sql')
    else:
        require(sql(project, "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_rocksdb';") == '0', 'Four-engine path has a MyRocks table')
    expected = [50000, sum(range(1, 50001)), sum(1+i % 500 for i in range(1, 50001)),
                sum(i % 196-15 for i in range(1, 50001)), 0, 0]
    for engine in engines:
        require(table_summary(project, engine) == expected, 'Wrong generated tutorial data')
        actual = sql(project, "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_"+engine+"';")
        require(actual.lower() == engine, 'Silent engine substitution')
    source(project, '03-compare.sql')
    if rocks:
        source(project, '03b-myrocks-compare.sql')
    source(project, '04-index-types.sql')
    indexes = check_indexes(project)
    source(project, '05-lock-demo.sql')
    rejected = check_invalid_inputs(project)
    singles = []
    for engine in engines:
        before = table_summary(project, engine)[4]
        item = hammer(project, engine, 1)
        require(table_summary(project, engine)[4] == before+item['updates'], 'Single-writer count differs from affected rows')
        singles.append(item)
    concurrent = [concurrent_writes(project, engine, same) for engine in ('aria', 'innodb') for same in (False, True)]
    lock_counters = sql(project, "SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited','Innodb_row_lock_waits');")
    snapshots = {engine: table_summary(project, engine) for engine in engines}
    identity(project)
    compose(project, 'restart', 'db')
    compose(project, 'up', '-d', '--wait', '--wait-timeout', '180', 'db')
    identity(project)
    source(project, '06-after-restart.sql')
    if rocks:
        source(project, '06b-myrocks-after-restart.sql')
    for engine in engines:
        if engine == 'memory':
            require(sql(project, 'SELECT COUNT(*) FROM tut_memory;') == '0', 'MEMORY rows unexpectedly persisted')
        else:
            require(table_summary(project, engine) == snapshots[engine], 'Persistent tutorial data changed across restart')
    source(project, '99-cleanup.sql')
    require(sql(project, "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND LEFT(TABLE_NAME,4)='tut_';") == '0', 'Tutorial table cleanup incomplete')
    require(sql(project, "SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME='tut_hammer';") == '0', 'Tutorial procedure cleanup incomplete')
    require(sql(project, 'SELECT note FROM ci_tutorial_sentinel WHERE id=1;') == 'preserve', 'Cleanup changed an unrelated table')
    return dict(engines=list(engines), rows_per_table=50000, indexes=indexes, rejected_inputs=rejected,
                single_writers=singles, concurrent_writers=concurrent, global_lock_counters=lock_counters,
                restart='persistent data preserved; MEMORY emptied', cleanup='tutorial objects removed; unrelated table preserved')


def run(project):
    validate_project(project)  # Before any Docker invocation, including inspection.
    identity(project)
    require(sql(project, "SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND (LEFT(TABLE_NAME,4)='tut_' OR TABLE_NAME='ci_tutorial_sentinel');") == '0', 'Existing tutorial objects; refusing to overwrite')
    require(sql(project, "SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME='tut_hammer';") == '0', 'Existing tutorial procedure; refusing to overwrite')
    version = sql(project, 'SELECT VERSION();')
    require('MariaDB' in version, 'MariaDB required')
    compose(project, 'exec', '-T', 'db', 'mkdir', '-p', '/tutorial')
    compose(project, 'cp', 'sql/tutorial/.', 'db:/tutorial/')
    sql(project, "CREATE TABLE ci_tutorial_sentinel (id INT PRIMARY KEY, note VARCHAR(32)); INSERT INTO ci_tutorial_sentinel VALUES (1,'preserve');")
    results = [run_sequence(project, rocks) for rocks in (True, False)]
    sql(project, 'DROP TABLE ci_tutorial_sentinel;')
    evidence = dict(experiment='tutorial_sql_correctness', commit=os.environ.get('GITHUB_SHA','local'),
                    platform=platform.platform(), host_python=sys.version, server_version=version,
                    source_sha256={name:hashlib.sha256((ROOT/'sql/tutorial'/name).read_bytes()).hexdigest() for name in FILES},
                    sequences=results, scope='Linux amd64 CI correctness; four-engine SQL tested on amd64, not native ARM; no performance evidence')
    print('TUTORIAL_VALIDATION_JSON_BEGIN', flush=True)
    print(json.dumps(evidence, indent=2), flush=True)
    print('TUTORIAL_VALIDATION_JSON_END', flush=True)
    print('TUTORIAL SMOKE PASS', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    args = parser.parse_args()
    try:
        run(args.project)
    except Exception as error:
        print('TUTORIAL SMOKE FAILED:', str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
