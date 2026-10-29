"""Shared SQL correctness checks for the five-engine lab and stock-image tutorial."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import math
import threading

from scripts.tutorial_transactions import check_transactions

ENGINES = ('innodb', 'aria', 'myisam', 'memory', 'rocksdb')
FILES = ('01-create-tables.sql', '02-myrocks.sql', '03-compare.sql', '03b-myrocks-compare.sql',
         '04-index-types.sql', '05-lock-demo.sql', '05b-transactions.sql',
         '05c-myrocks-transactions.sql', '06-after-restart.sql',
         '06b-myrocks-after-restart.sql', '99-cleanup.sql')
COMMON_FILES = tuple(name for name in FILES if name not in
                     ('02-myrocks.sql', '03b-myrocks-compare.sql', '05c-myrocks-transactions.sql',
                      '06b-myrocks-after-restart.sql'))
LOCK_COUNTERS = ('Table_locks_waited', 'Innodb_row_lock_waits')
LOCK_STATUS_SQL = "SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited','Innodb_row_lock_waits');"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def parse_lock_counters(output):
    """Do not turn unavailable, duplicate or malformed observations into zeroes."""
    counters = {}
    for row in output.splitlines():
        cells = row.split('\t')
        require(len(cells) == 2 and cells[0] in LOCK_COUNTERS and
                cells[0] not in counters, 'Unexpected tutorial lock-counter row')
        require(cells[1].isascii() and cells[1].isdecimal(),
                'Invalid tutorial lock-counter value')
        counters[cells[0]] = int(cells[1])
    require(set(counters) == set(LOCK_COUNTERS), 'Missing tutorial lock counters')
    return counters


def lock_counter_delta(before, after):
    require(set(before) == set(after) == set(LOCK_COUNTERS),
            'Missing tutorial lock counters')
    require(all(type(before[name]) is int and type(after[name]) is int and
                0 <= before[name] <= after[name] for name in LOCK_COUNTERS),
            'Tutorial lock counters reset or are invalid')
    return {name: after[name]-before[name] for name in LOCK_COUNTERS}


def server_interval(writer):
    try:
        started = datetime.fromisoformat(writer['server_started_at'])
        finished = datetime.fromisoformat(writer['server_finished_at'])
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError('Invalid tutorial server interval') from error
    require(started.tzinfo is None and finished.tzinfo is None and finished > started,
            'Invalid tutorial server interval')
    elapsed = writer['elapsed_seconds']
    require(math.isfinite(elapsed) and elapsed > 0 and
            abs((finished-started).total_seconds()-elapsed) <= 0.000001,
            'Tutorial elapsed time differs from server interval')
    return started, finished


def server_overlap(writers):
    """Compare SQL-recorded intervals, not host/Docker client launch times."""
    require(len(writers) == 2, 'Expected two tutorial writer intervals')
    intervals = [server_interval(writer) for writer in writers]
    seconds = max(0.0, (min(end for _, end in intervals)-
                        max(start for start, _ in intervals)).total_seconds())
    return dict(observed=seconds > 0, seconds=seconds,
                clock='server SYSDATE(6); same server, not client launch timestamps')


class TutorialChecks:
    """Use a supplied SQL client and guarded restart for the same tutorial checks."""

    def __init__(self, sql, restart):
        self.sql = sql
        self.restart = restart
        self.sourced_files = []

    def source(self, name):
        require(name in FILES, 'Unexpected tutorial source path')
        output = self.sql('source /tutorial/'+name)
        self.sourced_files.append(name)
        print('SQL PASS:', name, flush=True)
        return output

    def table_summary(self, engine):
        require(engine in ENGINES, 'Unknown engine')
        # Identifiers come only from the fixed engine whitelist, never from user input.
        out = self.sql('SELECT COUNT(*), SUM(id), SUM(airport_id), SUM(delay_min), SUM(hits), '
                  "SUM(id NOT BETWEEN 1 AND 50000 OR airport_id <> 1 + MOD(id,500) OR delay_min <> MOD(id,196)-15 OR note <> CONCAT('row-', id)) FROM tut_"+engine+';')
        return [int(v) for v in out.split('\t')]

    def hammer(self, engine, row_id, seconds=1):
        require(engine in ENGINES and type(row_id) is int and row_id in (1, 2) and
                type(seconds) is int and 1 <= seconds <= 60, 'Unexpected tutorial writer')
        out = self.sql("CALL tut_hammer('"+engine+"', "+str(row_id)+', '+str(seconds)+');')
        cells = out.split('\t')
        require(len(cells) == 7 and cells[0] == engine and int(cells[1]) == row_id, 'Unexpected writer result')
        require(int(cells[2]) > 0 and math.isfinite(float(cells[3])) and float(cells[3]) > 0,
                'No successful tutorial updates')
        writer = dict(engine=engine, row_id=row_id, updates=int(cells[2]),
                      elapsed_seconds=float(cells[3]), server_started_at=cells[5],
                      server_finished_at=cells[6])
        # Validate individual SQL intervals even for the single-writer checks.
        server_interval(writer)
        return writer

    def check_invalid_inputs(self):
        calls = ("CALL tut_hammer('innodb', 1, NULL);", "CALL tut_hammer('innodb', 1, 0);",
                 "CALL tut_hammer(NULL, 1, 1);", "CALL tut_hammer('unknown', 1, 1);",
                 "CALL tut_hammer('innodb', NULL, 1);", "CALL tut_hammer('innodb', 999999, 1);")
        for text in calls:
            try:
                self.sql(text)
            except RuntimeError as error:
                require('45000' in str(error), 'Expected a routine validation failure')
            else:
                raise RuntimeError('Invalid routine call was accepted')
        require(self.table_summary('innodb')[4] == 0, 'Rejected calls changed the data')
        return len(calls)

    def check_indexes(self):
        checks = []
        for index in ('btree', 'hash'):
            table = 'tut_idx_'+index
            actual = self.sql("SELECT INDEX_TYPE FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='"+table+"' AND INDEX_NAME='by_airport';")
            require(actual == index.upper(), 'Unexpected MEMORY index type')
            for predicate, expected, access in (('airport_id = 100', 20, 'ref'),
                                                 ('airport_id BETWEEN 100 AND 109', 200, 'range' if index == 'btree' else 'ALL')):
                require(int(self.sql('SELECT COUNT(*) FROM '+table+' WHERE '+predicate+';')) == expected, 'Wrong index-query answer')
                plan = self.sql('EXPLAIN SELECT COUNT(*) FROM '+table+' WHERE '+predicate+';').split('\t')
                require(len(plan) >= 6 and plan[3] == access, 'Unexpected index access path')
                checks.append(dict(index=index, predicate=predicate, count=expected, access=plan[3], key=plan[5]))
        return checks

    def concurrent_writes(self, engine, same_row):
        require(engine in ENGINES, 'Unexpected concurrent tutorial engine')
        ids = (1, 1) if same_row else (1, 2)
        before = {row: int(self.sql('SELECT hits FROM tut_'+engine+' WHERE id='+str(row)+';')) for row in set(ids)}
        lock_before = parse_lock_counters(self.sql(LOCK_STATUS_SQL))
        barrier = threading.Barrier(2)
        def work(row):
            barrier.wait(timeout=30)
            return self.hammer(engine, row)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work, row) for row in ids]
            writers = [f.result() for f in futures]
        lock_after = parse_lock_counters(self.sql(LOCK_STATUS_SQL))
        delta = lock_counter_delta(lock_before, lock_after)
        for row in set(ids):
            actual = int(self.sql('SELECT hits FROM tut_'+engine+' WHERE id='+str(row)+';'))
            require(actual == before[row]+sum(w['updates'] for w in writers if w['row_id'] == row), 'Concurrent increments were lost or miscounted')
        return dict(engine=engine, pattern='same row' if same_row else 'disjoint', writers=writers,
                    lock_before=lock_before, lock_after=lock_after, lock_delta=delta,
                    server_overlap=server_overlap(writers),
                    counter_scope='global server counters during this case; no wait-count threshold')

    def run_sequence(self, rocks):
        engines = ENGINES if rocks else ENGINES[:-1]
        self.source('01-create-tables.sql')
        if rocks:
            self.source('02-myrocks.sql')
        else:
            require(self.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_rocksdb';") == '0', 'Four-engine path has a MyRocks table')
        expected = [50000, sum(range(1, 50001)), sum(1+i % 500 for i in range(1, 50001)),
                    sum(i % 196-15 for i in range(1, 50001)), 0, 0]
        for engine in engines:
            require(self.table_summary(engine) == expected, 'Wrong generated tutorial data')
            actual = self.sql("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='tut_"+engine+"';")
            require(actual.lower() == engine, 'Silent engine substitution')
        self.source('03-compare.sql')
        if rocks:
            self.source('03b-myrocks-compare.sql')
        self.source('04-index-types.sql')
        indexes = self.check_indexes()
        self.source('05-lock-demo.sql')
        rejected = self.check_invalid_inputs()
        singles = []
        for engine in engines:
            before = self.table_summary(engine)[4]
            item = self.hammer(engine, 1)
            require(self.table_summary(engine)[4] == before+item['updates'], 'Single-writer count differs from affected rows')
            singles.append(item)
        concurrent = [self.concurrent_writes(engine, same) for engine in ('aria', 'innodb') for same in (False, True)]
        lock_counters = self.sql(LOCK_STATUS_SQL)
        transactions = check_transactions(self.source, rocks)
        snapshots = {engine: self.table_summary(engine) for engine in engines}
        self.restart()
        self.source('06-after-restart.sql')
        if rocks:
            self.source('06b-myrocks-after-restart.sql')
        for engine in engines:
            if engine == 'memory':
                require(self.sql('SELECT COUNT(*) FROM tut_memory;') == '0', 'MEMORY rows unexpectedly persisted')
            else:
                require(self.table_summary(engine) == snapshots[engine], 'Persistent tutorial data changed across restart')
        self.source('99-cleanup.sql')
        require(self.sql("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND LEFT(TABLE_NAME,4)='tut_';") == '0', 'Tutorial table cleanup incomplete')
        require(self.sql("SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA=DATABASE() AND ROUTINE_NAME='tut_hammer';") == '0', 'Tutorial procedure cleanup incomplete')
        require(self.sql('SELECT note FROM ci_tutorial_sentinel WHERE id=1;') == 'preserve', 'Cleanup changed an unrelated table')
        return dict(engines=list(engines), rows_per_table=50000, indexes=indexes, rejected_inputs=rejected,
                    single_writers=singles, concurrent_writers=concurrent, global_lock_counters=lock_counters,
                    transaction_semantics=transactions,
                    restart='persistent data preserved; MEMORY emptied', cleanup='tutorial objects removed; unrelated table preserved')
