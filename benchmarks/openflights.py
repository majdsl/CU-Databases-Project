"""Repeated, verified OpenFlights route load and warm-read comparison across five engines."""
import argparse
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import statistics
import sys
import time
import uuid

from .core import ENGINES, dataset_digest, describe, engine_schedule, lookup_ids, row_bytes
from .openflights_data import DATA, load_dataset
from .run import LOCK_NAME, ROOT, measure, runtime_metadata, save_json, source_fingerprint, variables

TABLE = 'openflights_routes'
COLUMNS = 'route_row_id, airline, airline_id, source_code, source_id, destination_code, destination_id, codeshare, stops, equipment'
INSERT = f'INSERT INTO {TABLE} ({COLUMNS}) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)'
SELECT_ALL = f'SELECT {COLUMNS} FROM {TABLE} ORDER BY route_row_id'
POINT = f'SELECT {COLUMNS} FROM {TABLE} WHERE route_row_id = %s'
SCAN = f'SELECT COUNT(*), COALESCE(SUM(stops),0), COALESCE(SUM(CHAR_LENGTH(equipment)),0) FROM {TABLE}'
SOURCE = f'SELECT COUNT(*), COALESCE(SUM(stops),0) FROM {TABLE} WHERE source_id = %s'


@dataclass(frozen=True)
class Config:
    pilot: bool = False
    seed: int = 20261009
    lookups: int = 200
    scans: int = 5
    source_queries: int = 100
    batch_size: int = 500

    @property
    def rounds(self):
        return 1 if self.pilot else 5

    def validate(self):
        if type(self.pilot) is not bool:
            raise ValueError('pilot must be boolean')
        for name in ('seed', 'lookups', 'scans', 'source_queries', 'batch_size'):
            if type(getattr(self, name)) is not int:
                raise ValueError(name + ' must be an integer')
        if not 10 <= self.lookups <= 10000 or not 2 <= self.scans <= 100:
            raise ValueError('lookups must be 10..10000; scans 2..100')
        if not 10 <= self.source_queries <= 1000 or not 1 <= self.batch_size <= 1000:
            raise ValueError('source queries must be 10..1000; batch size 1..1000')


def ddl(engine):
    if engine not in ENGINES:
        raise ValueError('Unknown engine')
    return (ROOT / 'sql/openflights' / (engine.lower() + '.sql')).read_text(encoding='utf-8')


def oracles(rows):
    sources = defaultdict(lambda: [0, 0])
    for row in rows:
        if row[4] is not None:
            sources[row[4]][0] += 1
            sources[row[4]][1] += row[8]
    scan = (len(rows), sum(r[8] for r in rows), sum(len(r[9]) for r in rows))
    return scan, {key: tuple(value) for key, value in sources.items()}


def query_streams(config, round_index, rows, sources):
    keys = lookup_ids(config.seed, round_index, len(rows), config.lookups)
    possible = sorted(sources)
    if not possible:
        raise ValueError('No non-null source IDs')
    indices = lookup_ids(config.seed + 77, round_index, len(possible), config.source_queries)
    return keys, [possible[i - 1] for i in indices]


def verify_rows(cursor, expected):
    cursor.execute(SELECT_ALL)
    digest = hashlib.sha256()
    position = 0
    while batch := cursor.fetchmany(1000):
        for actual in batch:
            if position >= len(expected) or tuple(actual) != expected[position]:
                raise RuntimeError('OpenFlights row mismatch, extra row or wrong ordering')
            digest.update(row_bytes(actual)); position += 1
    if position != len(expected):
        raise RuntimeError('Missing OpenFlights rows')
    return digest.hexdigest()


def trial(connection, engine, config, rows, round_index, scan, sources):
    with connection.cursor() as cursor:
        cursor.execute('SELECT TABLE_NAME FROM information_schema.TABLES '
                       'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s', (TABLE,))
        if cursor.fetchone() is not None:
            raise RuntimeError('openflights_routes already exists; refusing to overwrite it')
        cursor.execute(ddl(engine))
        # Failed trials deliberately retain this table for inspection. No retries or repair.
        cursor.execute('SELECT ENGINE FROM information_schema.TABLES '
                       'WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s', (TABLE,))
        actual = cursor.fetchone()
        if actual is None or actual[0].lower() != engine.lower():
            raise RuntimeError('Engine substitution detected')
        cursor.execute(f'SHOW CREATE TABLE {TABLE}'); actual_ddl = cursor.fetchone()[1]
        started = time.perf_counter_ns()
        for offset in range(0, len(rows), config.batch_size):
            cursor.executemany(INSERT, rows[offset:offset + config.batch_size])
        load_seconds = (time.perf_counter_ns() - started) / 1e9
        cursor.execute(f'ANALYZE TABLE {TABLE}'); analyze = cursor.fetchall()
        if any(str(r[2]).lower() == 'error' for r in analyze):
            raise RuntimeError('ANALYZE TABLE failed: ' + str(analyze))
        digest = verify_rows(cursor, rows)
        if digest != dataset_digest(rows):
            raise RuntimeError('Dataset checksum mismatch')
        keys, source_ids = query_streams(config, round_index, rows, sources)
        for key in keys[:50]:
            measure(cursor, POINT, (key,), rows[key - 1])
        measure(cursor, SCAN, None, scan)
        for key in source_ids[:20]:
            measure(cursor, SOURCE, (key,), sources[key])
        timings = dict(lookup_ms=[measure(cursor, POINT, (key,), rows[key - 1]) for key in keys],
            scan_ms=[measure(cursor, SCAN, None, scan) for _ in range(config.scans)],
            source_ms=[measure(cursor, SOURCE, (key,), sources[key]) for key in source_ids])
        plans = {}
        for label, statement, params in [('point', POINT, (keys[0],)), ('scan', SCAN, None),
                                          ('source', SOURCE, (source_ids[0],))]:
            cursor.execute('EXPLAIN ' + statement, params); plans[label] = cursor.fetchall()
        item = dict(engine=engine, round=round_index + 1, load_seconds=load_seconds,
            verified_rows=len(rows), verified_dataset_sha256=digest, actual_ddl=actual_ddl,
            analyze_messages=analyze, explain=plans, lookup_ids=keys, source_ids=source_ids,
            source_result_counts=[sources[k][0] for k in source_ids], **timings)
        cursor.execute(f'DROP TABLE {TABLE}')  # Only the successfully created and verified trial table.
        return item


def summarize(result):
    config = Config(**result['config']); config.validate()
    expected_order = engine_schedule(config.seed, 5)[:config.rounds]
    if result['status'] != 'completed' or result['schedule'] != expected_order:
        raise ValueError('Only a completed, correctly scheduled run can be summarized')
    triples = [(round_number, position, engine) for round_number, order in enumerate(expected_order, 1)
               for position, engine in enumerate(order, 1)]
    if [(t['round'], t['position'], t['engine']) for t in result['trials']] != triples:
        raise ValueError('Missing, repeated or out-of-order trials')
    for trial_result in result['trials']:
        if (trial_result['verified_rows'] != result['rows']
                or trial_result['verified_dataset_sha256'] != result['dataset_sha256']):
            raise ValueError('Unverified trial')
        for field, count in [('lookup_ms', config.lookups), ('scan_ms', config.scans),
                             ('source_ms', config.source_queries)]:
            if len(trial_result[field]) != count:
                raise ValueError('Missing timing samples')
            describe(trial_result[field])
    summary = {}
    for engine in ENGINES:
        trials = [t for t in result['trials'] if t['engine'] == engine]
        summary[engine] = {'load_seconds': describe([t['load_seconds'] for t in trials])}
        for metric in ('lookup_ms', 'scan_ms', 'source_ms'):
            summary[engine][metric] = describe([statistics.mean(t[metric]) for t in trials])
    return summary


def markdown(result):
    stats = summarize(result)
    lines = ['# OpenFlights route comparison', '', f"Run: {result['run_id']}", '',
        ('**PILOT: one round per engine; no variability estimate or ranking.**' if result['config']['pilot']
         else '**FULL: five balanced engine-order rounds; statistical unit = one trial/round.**'), '',
        f"Rows per trial: {result['rows']}. Power condition: {result['power_condition']}.",
        'Read statistics summarize round means, not pooled individual queries. Values are mean ± sample SD.', '',
        '| Engine | Load (s) | Point lookup (ms) | Full scan (ms) | Source aggregate (ms) |',
        '| --- | ---: | ---: | ---: | ---: |']
    def cell(stat):
        sd = 'n/a' if stat['sample_sd'] is None else f"{stat['sample_sd']:.4f}"
        return f"{stat['mean']:.4f} ± {sd}"
    for engine in ENGINES:
        lines.append('| ' + engine + ' | ' + ' | '.join(cell(stats[engine][metric])
            for metric in ('load_seconds', 'lookup_ms', 'scan_ms', 'source_ms')) + ' |')
    lines += ['', 'Every row and query answer was checked. Raw samples, query streams, plans, actual DDL,',
        'dataset/source hashes and runtime/settings metadata are in results.json.',
        'These are warm reads on a reused server. Timings include driver/network work; durability and',
        'cache budgets are not equalized. No physical-disk, cold-cache or steady-state claim is made.',
        'The routes snapshot is historical reference data, not observed flights or current schedules.',
        'Keep these results separate from synthetic events and the pilot separate from full statistics.',
        'Data: OpenFlights, via MariaDB/openflights; ODbL 1.0. See docs/openflights-method.md.', '']
    return '\n'.join(lines)


def run(config, output, power_condition):
    config.validate()
    if os.environ.get('DB_NAME') != 'engine_lab':
        raise ValueError('Only the dedicated engine_lab database is allowed')
    if not power_condition.strip():
        raise ValueError('Record the actual power condition')
    manifest, rows = load_dataset()
    scan, sources = oracles(rows)
    import pymysql
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-openflights-' + uuid.uuid4().hex[:8]
    directory = output / run_id; directory.mkdir(parents=True, exist_ok=False)
    fingerprints = source_fingerprint()
    for path in list((ROOT / 'sql/openflights').glob('*.sql')) + [DATA / 'manifest.json', ROOT / 'scripts/fetch_openflights.py']:
        fingerprints[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = dict(format_version=1, experiment='openflights_routes_v1', status='running', run_id=run_id,
        config=asdict(config), rows=len(rows), dataset=manifest, dataset_sha256=dataset_digest(rows),
        scan_oracle=scan, schedule=engine_schedule(config.seed, 5)[:config.rounds], trials=[],
        source_sha256=fingerprints, runtime=runtime_metadata(), power_condition=power_condition,
        cache_condition='post-load, post-analyze, full verification read, explicit query warmup')
    path = directory / 'results.json'; save_json(path, result)
    try:
        with pymysql.connect(host=os.environ['DB_HOST'], user=os.environ['DB_USER'],
                password=os.environ['DB_PASSWORD'], database='engine_lab', charset='utf8mb4',
                autocommit=True, connect_timeout=10, read_timeout=300, write_timeout=300) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT GET_LOCK(%s, 0)', (LOCK_NAME,))
                if cursor.fetchone()[0] != 1:
                    raise RuntimeError('Another experiment holds the shared database lock')
                cursor.execute('SELECT VERSION()'); result['server_version'] = cursor.fetchone()[0]
                if 'MariaDB' not in result['server_version']:
                    raise RuntimeError('MariaDB required')
                cursor.execute('SHOW ENGINES')
                available = {r[0].lower(): r[1].upper() for r in cursor.fetchall()}
                if any(available.get(e.lower()) not in ('YES', 'DEFAULT') for e in ENGINES):
                    raise RuntimeError('All five engines must be available')
                cursor.execute("SET SESSION sql_mode = 'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
                cursor.execute('SET SESSION query_cache_type = OFF')
                cursor.execute('SET SESSION max_heap_table_size = 134217728')
                result['global_variables'] = variables(cursor, 'global')
                result['session_variables'] = variables(cursor, 'session')
            save_json(path, result)
            for round_index, order in enumerate(result['schedule']):
                for position, engine in enumerate(order, 1):
                    print(f'OpenFlights round {round_index+1}/{config.rounds}: {engine}', flush=True)
                    result['active_trial'] = dict(engine=engine, round=round_index+1, position=position)
                    save_json(path, result)
                    item = trial(connection, engine, config, rows, round_index, scan, sources)
                    item['position'] = position; result['trials'].append(item)
                    del result['active_trial']; save_json(path, result)
        result['status'] = 'completed'; result['statistics'] = summarize(result)
        report = markdown(result)
        (directory / 'summary.md').write_text(report, encoding='utf-8')
        save_json(path, result); print(report); print('Saved:', directory)
    except (Exception, KeyboardInterrupt) as error:
        result['status'] = 'failed'; result['error_type'] = type(error).__name__
        (directory / 'summary.md').unlink(missing_ok=True); save_json(path, result)
        print('Partial results:', directory, file=sys.stderr)
        print('An owned failed-trial table may remain; inspect it before any retry.', file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--pilot', action='store_true'); mode.add_argument('--full', action='store_true')
    parser.add_argument('--power-condition', required=True)
    parser.add_argument('--output', type=Path, default=Path('/results'))
    args = parser.parse_args()
    try:
        run(Config(pilot=args.pilot), args.output, args.power_condition)
    except (Exception, KeyboardInterrupt) as error:
        print('FAILED:', str(error), file=sys.stderr); return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
