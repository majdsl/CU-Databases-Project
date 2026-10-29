"""Controlled MEMORY secondary-index comparison; warm single-client reads."""
import argparse
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import random
import statistics
import sys
import time
import uuid

from .core import dataset_digest, describe, row_bytes
from .run import LOCK_NAME, measure, runtime_metadata, save_json, source_fingerprint, variables

TABLE = 'memory_index_probe'
DDL = {
    'HASH': 'CREATE TABLE memory_index_probe (id INT NOT NULL, k INT NOT NULL, v INT NOT NULL, PRIMARY KEY (id) USING BTREE, KEY probe_k (k) USING HASH) ENGINE=MEMORY',
    'BTREE': 'CREATE TABLE memory_index_probe (id INT NOT NULL, k INT NOT NULL, v INT NOT NULL, PRIMARY KEY (id) USING BTREE, KEY probe_k (k) USING BTREE) ENGINE=MEMORY',
}
POINT = 'SELECT COUNT(*), COALESCE(SUM(v),0) FROM memory_index_probe WHERE k = %s'
RANGE = 'SELECT COUNT(*), COALESCE(SUM(v),0) FROM memory_index_probe WHERE k BETWEEN %s AND %s'
QUERIES = {'equality': POINT, 'range_10': RANGE, 'range_1000': RANGE}


@dataclass(frozen=True)
class Config:
    mode: str = 'pilot'
    seed: int = 20261016

    def validate(self):
        if self.mode not in ('pilot', 'full', 'smoke') or type(self.seed) is not int:
            raise ValueError('Invalid experiment configuration')

    @property
    def sizes(self):
        return (1000, 2000) if self.mode == 'smoke' else (10000, 100000)

    @property
    def rounds(self):
        return {'pilot': 1, 'full': 6, 'smoke': 2}[self.mode]

    @property
    def samples(self):
        return {'pilot': 20, 'full': 100, 'smoke': 3}[self.mode]


def schedule(config):
    config.validate()
    items = []
    for r in range(config.rounds):
        sizes = config.sizes if r % 2 == 0 else config.sizes[::-1]
        order = ('HASH', 'BTREE') if r % 2 == 0 else ('BTREE', 'HASH')
        for size in sizes:
            for position, index in enumerate(order, 1):
                items.append(dict(round=r+1, rows=size, position=position, index=index))
    return items


def dataset(size, seed):
    keys = list(range(1, size+1))
    random.Random(seed + size).shuffle(keys)
    return [(i, key, (i * 17) % 1009) for i, key in enumerate(keys, 1)]


def streams(config, size, round_number):
    rng = random.Random(config.seed + size + 1000003 * round_number)
    result = {'equality': [(rng.randint(1, size),) for _ in range(config.samples)]}
    for width in (10, 1000):
        starts = [rng.randint(1, size-width+1) for _ in range(config.samples)]
        result['range_' + str(width)] = [(start, start+width-1) for start in starts]
    return result


def oracle(rows, query_streams):
    values = {r[1]: r[2] for r in rows}
    return {label: [(p[-1]-p[0]+1, sum(values[k] for k in range(p[0], p[-1]+1)))
                    for p in params] for label, params in query_streams.items()}


def verify_rows(cursor, rows):
    cursor.execute('SELECT id,k,v FROM memory_index_probe ORDER BY id')
    digest = hashlib.sha256(); n = 0
    while batch := cursor.fetchmany(1000):
        for actual in batch:
            if n >= len(rows) or tuple(actual) != rows[n]:
                raise RuntimeError('Loaded row mismatch')
            digest.update(row_bytes(actual)); n += 1
    if n != len(rows):
        raise RuntimeError('Missing loaded rows')
    return digest.hexdigest()


def records(cursor):
    names = [d[0] for d in cursor.description]
    return [dict(zip(names, row)) for row in cursor.fetchall()]


def verify_indexes(indexes, variant):
    actual = {(r['Key_name'], r['Column_name'], r['Index_type'].upper()) for r in indexes}
    if len(indexes) != 2 or actual != {('PRIMARY', 'id', 'BTREE'), ('probe_k', 'k', variant)}:
        raise RuntimeError('Actual index definitions differ from experiment')


def handlers(cursor):
    cursor.execute('SHOW SESSION STATUS')
    return {k: int(v) for k, v in cursor.fetchall() if k.startswith('Handler_read_')}


def diagnostic(cursor, statement, params, expected):
    cursor.execute('EXPLAIN ' + statement, params)
    plan = records(cursor)
    before = handlers(cursor)
    measure(cursor, statement, params, expected)  # separate untimed replay, not a timing sample
    after = handlers(cursor)
    if before.keys() != after.keys() or any(after[k] < before[k] for k in before):
        raise RuntimeError('Invalid session handler counter delta')
    return {'parameters': params, 'explain': plan,
            'handler_read_delta': {k: after[k]-before[k] for k in before}}


def trial(connection, config, item):
    rows = dataset(item['rows'], config.seed)
    query_streams = streams(config, item['rows'], item['round'])
    answers = oracle(rows, query_streams)
    variant = item['index']
    with connection.cursor() as cursor:
        cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (TABLE,))
        if cursor.fetchone() is not None:
            raise RuntimeError('memory_index_probe exists; refusing to change it')
        cursor.execute(DDL[variant])
        # Retain any failed table for inspection. Never drop a pre-existing table.
        cursor.execute('SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s', (TABLE,))
        engine = cursor.fetchone()
        if not engine or engine[0].upper() != 'MEMORY':
            raise RuntimeError('Engine substitution')
        cursor.execute('SHOW INDEX FROM memory_index_probe'); indexes = records(cursor)
        verify_indexes(indexes, variant)
        cursor.execute('SHOW CREATE TABLE memory_index_probe'); actual_ddl = cursor.fetchone()[1]
        start = time.perf_counter_ns()
        for offset in range(0, len(rows), 500):
            cursor.executemany('INSERT INTO memory_index_probe (id,k,v) VALUES (%s,%s,%s)', rows[offset:offset+500])
        load_seconds = (time.perf_counter_ns()-start)/1e9
        digest = verify_rows(cursor, rows)
        timings = {}; diagnostics = {}
        for label, statement in QUERIES.items():
            params = query_streams[label]; expected = answers[label]
            for p, answer in list(zip(params, expected))[:5]:
                measure(cursor, statement, p, answer)
            timings[label] = [measure(cursor, statement, p, answer) for p, answer in zip(params, expected)]
            diagnostics[label] = diagnostic(cursor, statement, params[0], expected[0])
        cursor.execute("SHOW TABLE STATUS WHERE Name='memory_index_probe'")
        status = records(cursor)
        result = dict(item, load_seconds=load_seconds, verified_rows=len(rows),
                      verified_dataset_sha256=digest, actual_ddl=actual_ddl, actual_indexes=indexes,
                      query_streams=query_streams, answers=answers, timings_ms=timings,
                      diagnostics=diagnostics, engine_reported_table_status=status)
        cursor.execute('DROP TABLE memory_index_probe')
        return result


def summarize(result):
    config = Config(**result['config']); config.validate()
    expected = schedule(config)
    if result['status'] != 'completed' or result['schedule'] != expected:
        raise ValueError('Incomplete or invalid run')
    if [{k: t[k] for k in ('round','rows','position','index')} for t in result['trials']] != expected:
        raise ValueError('Missing, duplicate or reordered trials')
    for t in result['trials']:
        verify_indexes(t['actual_indexes'], t['index'])
        rows = dataset(t['rows'], config.seed)
        if t['verified_rows'] != len(rows) or t['verified_dataset_sha256'] != dataset_digest(rows):
            raise ValueError('Unverified dataset')
        expected_streams = streams(config, t['rows'], t['round'])
        expected_answers = oracle(rows, expected_streams)
        for label in QUERIES:
            if [tuple(p) for p in t['query_streams'][label]] != expected_streams[label]:
                raise ValueError('Changed query stream')
            if [tuple(a) for a in t['answers'][label]] != expected_answers[label]:
                raise ValueError('Changed answers')
            if len(t['timings_ms'][label]) != config.samples:
                raise ValueError('Missing samples')
            describe(t['timings_ms'][label])
        describe([t['load_seconds']])
    stats = {}
    for size in config.sizes:
        stats[str(size)] = {}
        for index in DDL:
            trials = [t for t in result['trials'] if t['rows'] == size and t['index'] == index]
            stats[str(size)][index] = {label: describe([statistics.mean(t['timings_ms'][label]) for t in trials]) for label in QUERIES}
    return stats


def markdown(result):
    stats = summarize(result)
    lines = ['# MEMORY HASH versus BTREE', '', 'Mode: ' + result['config']['mode'],
             'Warm single-client reads. Statistical unit: trial mean; mean ± sample SD in ms.',
             'Pilot/smoke runs do not support performance conclusions.', '',
             '| Rows | Index | Equality | Range 10 | Range 1000 |', '| ---: | --- | ---: | ---: | ---: |']
    for size, variants in stats.items():
        for index, metrics in variants.items():
            cells = []
            for stat in metrics.values():
                sd = 'n/a' if stat['sample_sd'] is None else f"{stat['sample_sd']:.4f}"
                cells.append(f"{stat['mean']:.4f} ± {sd}")
            lines.append('| ' + ' | '.join([size,index]+cells) + ' |')
    lines += ['', 'Only the secondary index type changes. Same rows and query stream within each round/size pair.',
              'All rows and answers verified; actual indexes, plans and separate session Handler_read deltas saved.',
              'Timings include driver/network overhead. No cold-cache, concurrency or general engine-ranking claim.',
              'Inspect plans and counters before attributing a timing difference to an access method.', '']
    return '\n'.join(lines)


def run(config, output, power):
    config.validate()
    if os.environ.get('DB_NAME') != 'engine_lab' or not power.strip():
        raise ValueError('Dedicated engine_lab and recorded power condition required')
    import pymysql
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-memory-indexes-' + uuid.uuid4().hex[:8]
    directory = output / run_id; directory.mkdir(parents=True, exist_ok=False)
    result = dict(format_version=1, experiment='memory_indexes_v1', run_id=run_id,
                  config=asdict(config), status='running', schedule=schedule(config), trials=[],
                  power_condition=power, runtime=runtime_metadata(), source_sha256=source_fingerprint())
    path = directory / 'results.json'; save_json(path, result)
    try:
        with pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'], password=os.environ['DB_PASSWORD'],
                database='engine_lab', charset='utf8mb4', autocommit=True, connect_timeout=10,
                read_timeout=300, write_timeout=300) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT GET_LOCK(%s,0)', (LOCK_NAME,))
                if cursor.fetchone()[0] != 1:
                    raise RuntimeError('Another experiment holds the database lock')
                cursor.execute('SELECT VERSION()'); result['server_version'] = cursor.fetchone()[0]
                if 'MariaDB' not in result['server_version']:
                    raise RuntimeError('MariaDB required')
                cursor.execute("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
                cursor.execute('SET SESSION query_cache_type=OFF')
                cursor.execute('SET SESSION max_heap_table_size=134217728')
                result['global_variables'] = variables(cursor, 'global')
                result['session_variables'] = variables(cursor, 'session')
            save_json(path, result)
            for item in result['schedule']:
                print('MEMORY:', item, flush=True)
                result['active_trial'] = item; save_json(path, result)
                result['trials'].append(trial(connection, config, item))
                del result['active_trial']; save_json(path, result)
        result['status'] = 'completed'; result['statistics'] = summarize(result)
        report = markdown(result)
        (directory/'summary.md').write_text(report, encoding='utf-8')
        save_json(path, result); print(report); print('Saved:', directory)
    except (Exception, KeyboardInterrupt) as error:
        result['status'] = 'failed'; result['error_type'] = type(error).__name__
        (directory/'summary.md').unlink(missing_ok=True); save_json(path, result)
        print('Partial results:', directory, file=sys.stderr)
        print('A failed memory_index_probe table may remain. Inspect before retrying.', file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    for name in ('pilot','full','smoke'):
        mode.add_argument('--'+name, action='store_true')
    parser.add_argument('--power-condition', required=True)
    parser.add_argument('--output', type=Path, default=Path('/results'))
    args = parser.parse_args()
    chosen = 'pilot' if args.pilot else 'full' if args.full else 'smoke'
    try:
        run(Config(chosen), args.output, args.power_condition)
    except (Exception, KeyboardInterrupt) as error:
        print('FAILED:', str(error), file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
