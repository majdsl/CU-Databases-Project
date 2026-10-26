"""Shared SQL correctness checks for the five-engine lab and stock-image tutorial."""
from concurrent.futures import ThreadPoolExecutor
import threading

ENGINES = ('innodb', 'aria', 'myisam', 'memory', 'rocksdb')
FILES = ('01-create-tables.sql', '02-myrocks.sql', '03-compare.sql', '03b-myrocks-compare.sql',
         '04-index-types.sql', '05-lock-demo.sql', '06-after-restart.sql',
         '06b-myrocks-after-restart.sql', '99-cleanup.sql')
COMMON_FILES = tuple(name for name in FILES if name not in
                     ('02-myrocks.sql', '03b-myrocks-compare.sql', '06b-myrocks-after-restart.sql'))


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


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
        require(engine in ENGINES and row_id in (1, 2), 'Unexpected tutorial writer')
        out = self.sql("CALL tut_hammer('"+engine+"', "+str(row_id)+', '+str(seconds)+');')
        cells = out.split('\t')
        require(len(cells) == 5 and cells[0] == engine and int(cells[1]) == row_id, 'Unexpected writer result')
        require(int(cells[2]) > 0 and float(cells[3]) > 0, 'No successful tutorial updates')
        return dict(engine=engine, row_id=row_id, updates=int(cells[2]), elapsed_seconds=float(cells[3]))

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
        ids = (1, 1) if same_row else (1, 2)
        before = {row: int(self.sql('SELECT hits FROM tut_'+engine+' WHERE id='+str(row)+';')) for row in set(ids)}
        barrier = threading.Barrier(2)
        def work(row):
            barrier.wait(timeout=30)
            return self.hammer(engine, row)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(work, row) for row in ids]
            writers = [f.result() for f in futures]
        for row in set(ids):
            actual = int(self.sql('SELECT hits FROM tut_'+engine+' WHERE id='+str(row)+';'))
            require(actual == before[row]+sum(w['updates'] for w in writers if w['row_id'] == row), 'Concurrent increments were lost or miscounted')
        return dict(engine=engine, pattern='same row' if same_row else 'disjoint', writers=writers)

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
        lock_counters = self.sql("SHOW GLOBAL STATUS WHERE Variable_name IN ('Table_locks_waited','Innodb_row_lock_waits');")
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
                    restart='persistent data preserved; MEMORY emptied', cleanup='tutorial objects removed; unrelated table preserved')
