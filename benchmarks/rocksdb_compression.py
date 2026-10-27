"""Verified MyRocks compression trial and offline result validation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import statistics
import time
import zlib

from .core import describe
from .run import LOCK_NAME, measure, runtime_metadata, source_fingerprint, variables

SEED = 20261027
PAYLOAD_BYTES = 1024
BLOCK_CACHE_BYTES = 128 * 1048576
WRITE_BUFFER_BYTES = 16 * 1048576
PROFILES = ('compressible', 'random')
CODECS = {'none': 'kNoCompression', 'zstd': 'kZSTD'}
CONDITIONS = [(profile, codec) for profile in PROFILES for codec in CODECS]
# Four-condition Williams design: positions and pairwise order are balanced.
ORDERS = ((0, 1, 3, 2), (1, 2, 0, 3), (2, 3, 1, 0), (3, 0, 2, 1))
SST_NAME = re.compile(r'[0-9]+\.sst\Z')
DDL = ('CREATE TABLE compression_rows (id INT NOT NULL, '
       'payload VARBINARY(1024) NOT NULL, PRIMARY KEY (id)) ENGINE=ROCKSDB')
POINT = 'SELECT payload FROM compression_rows WHERE id=%s'
SCAN = 'SELECT COUNT(*), COALESCE(SUM(CRC32(payload)),0) FROM compression_rows'
SST_QUERY = (
    'SELECT SP.* FROM information_schema.ROCKSDB_SST_PROPS SP '
    'JOIN information_schema.ROCKSDB_INDEX_FILE_MAP IFM ON IFM.SST_NAME=SP.SST_NAME '
    'JOIN information_schema.ROCKSDB_DDL D ON D.INDEX_NUMBER=IFM.INDEX_NUMBER '
    'WHERE D.TABLE_SCHEMA=%s AND D.TABLE_NAME=%s ORDER BY SP.SST_NAME'
)


def settings(mode):
    if mode not in ('smoke', 'pilot', 'full'):
        raise ValueError('Unknown compression mode')
    return dict(rows=256 if mode == 'smoke' else 65536,
                rounds=8 if mode == 'full' else 1,
                lookups=12 if mode == 'smoke' else 200 if mode == 'pilot' else 1000,
                scans=1 if mode == 'smoke' else 3 if mode == 'pilot' else 5,
                warmups=4 if mode == 'smoke' else 50)


def schedule(mode):
    return [dict(round=r + 1, position=p + 1, profile=CONDITIONS[i][0],
                 codec=CONDITIONS[i][1])
            for r in range(settings(mode)['rounds'])
            for p, i in enumerate(ORDERS[r % len(ORDERS)])]


def cf_configuration(codec):
    if codec not in CODECS:
        raise ValueError('Unsupported codec')
    return (f'compression={CODECS[codec]};bottommost_compression={CODECS[codec]};'
            f'write_buffer_size={WRITE_BUFFER_BYTES};disable_auto_compactions=true')


def payload(profile, key):
    if profile not in PROFILES or key < 1:
        raise ValueError('Invalid data identity')
    if profile == 'random':
        return hashlib.shake_256(f'{SEED}:{key}'.encode()).digest(PAYLOAD_BYTES)
    prefix = f'flight:{key:08d}|route:{key % 500:03d}|'.encode()
    text = prefix + b'OpenFlights reference payload; reproducible synthetic compression control.|'
    return (text * (PAYLOAD_BYTES // len(text) + 1))[:PAYLOAD_BYTES]


def digest_row(digest, key, value):
    digest.update(key.to_bytes(8, 'big'))
    digest.update(value)


def oracle(profile, rows):
    digest = hashlib.sha256()
    crc_sum = 0
    for key in range(1, rows + 1):
        value = payload(profile, key)
        digest_row(digest, key, value)
        crc_sum += zlib.crc32(value)
    return dict(dataset_sha256=digest.hexdigest(), crc32_sum=crc_sum)


def query_ids(rows, round_number, count, warm=False):
    rng = random.Random(SEED + round_number * 1000003 + (71 if warm else 0))
    return [rng.randint(1, rows) for _ in range(count)]


def verify_stream(cursor, profile, rows, expected):
    digest = hashlib.sha256()
    count = 0
    crc_sum = 0
    cursor.execute('SELECT id,payload FROM compression_rows ORDER BY id')
    while batch := cursor.fetchmany(500):
        for key, value in batch:
            count += 1
            if key != count or value != payload(profile, count):
                raise RuntimeError('Row identity or payload differs from the oracle')
            digest_row(digest, key, value)
            crc_sum += zlib.crc32(value)
    if count != rows or digest.hexdigest() != expected['dataset_sha256'] or crc_sum != expected['crc32_sum']:
        raise RuntimeError('Incomplete or corrupt dataset')
    return count


def codec_name(value):
    name = str(value).lower()
    if name.startswith('k'):
        name = name[1:]
    if name.endswith('compression'):
        name = name[:-len('compression')]
    return 'none' if name in ('no', 'none') else name


def validate_options(options, codec):
    for key in ('COMPRESSION_TYPE', 'BOTTOMMOST_COMPRESSION'):
        if codec_name(options.get(key)) != codec:
            raise ValueError('Actual column-family compression differs: ' + key)
    if str(options.get('COMPRESSION_PER_LEVEL')).lower() not in ('', 'nul', 'null', '[]', 'none'):
        raise ValueError('Per-level compression would override the selected codec')
    if int(options.get('WRITE_BUFFER_SIZE', -1)) != WRITE_BUFFER_BYTES:
        raise ValueError('Write-buffer size differs')
    if str(options.get('DISABLE_AUTO_COMPACTIONS')).lower() not in ('1', 'true', 'on'):
        raise ValueError('Automatic compaction must be disabled for this flush-only study')


def cf_options(cursor):
    cursor.execute('SELECT OPTION_TYPE,VALUE FROM information_schema.ROCKSDB_CF_OPTIONS '
                   'WHERE CF_NAME=%s ORDER BY OPTION_TYPE', ('default',))
    return dict(cursor.fetchall())


def sst_snapshot(cursor, codec, rows):
    cursor.execute(SST_QUERY, ('engine_lab', 'compression_rows'))
    names = [column[0].upper() for column in cursor.description]
    unique = {}
    for row in cursor.fetchall():
        item = dict(zip(names, row))
        name = item['SST_NAME']
        if name in unique and unique[name] != item:
            raise RuntimeError('Conflicting properties for one SST')
        unique[name] = item
    result = [unique[name] for name in sorted(unique)]
    validate_ssts(result, codec, rows)
    return result


def validate_ssts(ssts, codec, rows):
    if not ssts or len({s['SST_NAME'] for s in ssts}) != len(ssts):
        raise ValueError('Missing or duplicate table SST files')
    if any(not SST_NAME.fullmatch(s['SST_NAME']) or codec_name(s['COMPRESSION_ALGO']) != codec
           for s in ssts):
        raise ValueError('Unexpected SST name or compression algorithm')
    if sum(int(s['ENTRIES']) for s in ssts) != rows:
        raise ValueError('SST entries do not cover the verified insert-only table')


def inventory(root=Path('/snapshot')):
    directory = root / '#rocksdb'
    if not directory.is_dir() or directory.is_symlink():
        raise RuntimeError('Missing regular MyRocks data directory')
    files = []
    for p in sorted(directory.glob('*.sst')):
        if p.is_symlink() or not p.is_file() or not SST_NAME.fullmatch(p.name):
            raise RuntimeError('Unexpected SST filesystem entry')
        stat = p.stat()
        files.append(dict(name=p.name, bytes=stat.st_size,
                          allocated_bytes=stat.st_blocks * 512))
    return files


def match_inventory(ssts, files):
    mapped = {item['name']: item for item in files}
    if len(mapped) != len(files):
        raise ValueError('Duplicate inventory file')
    selected = []
    for sst in ssts:
        name = sst['SST_NAME']
        if name not in mapped or mapped[name]['bytes'] <= 0:
            raise ValueError('Live table SST missing from stopped-volume inventory')
        selected.append(mapped[name])
    if len({s['name'] for s in selected}) != len(selected):
        raise ValueError('Duplicate mapped table file')
    return dict(files=selected, bytes=sum(s['bytes'] for s in selected),
                allocated_bytes=sum(s['allocated_bytes'] for s in selected))


def trial(mode, profile, codec, round_number):
    config = settings(mode)
    if profile not in PROFILES or codec not in CODECS or not 1 <= round_number <= config['rounds']:
        raise ValueError('Invalid trial')
    if (os.environ.get('COMPRESSION_EXPERIMENT') != 'isolated-v1' or
            os.environ.get('DB_NAME') != 'engine_lab' or os.environ.get('DB_HOST') != '127.0.0.1'):
        raise ValueError('Use the isolated host orchestrator')
    import pymysql
    rows = config['rows']
    expected = oracle(profile, rows)
    result = dict(mode=mode, profile=profile, codec=codec, round=round_number,
                  rows=rows, payload_bytes=PAYLOAD_BYTES, seed=SEED,
                  runtime=runtime_metadata(), source_sha256=source_fingerprint(), **expected)
    connect = dict(host='127.0.0.1', database='engine_lab', autocommit=True,
                   connect_timeout=10, read_timeout=600, write_timeout=600)
    with pymysql.connect(user='root', password=os.environ['COMPRESSION_ADMIN_PASSWORD'], **connect) as admin:
        with admin.cursor() as control:
            control.execute('SELECT VERSION()')
            result['server_version'] = control.fetchone()[0]
            if not result['server_version'].startswith('11.8.9-MariaDB'):
                raise RuntimeError('Expected the pinned MariaDB 11.8.9 build')
            control.execute("SELECT SUPPORT FROM information_schema.ENGINES WHERE ENGINE='ROCKSDB'")
            if control.fetchone() not in (('YES',), ('DEFAULT',)):
                raise RuntimeError('MyRocks is unavailable')
            control.execute('SHOW GLOBAL VARIABLES')
            result['rocksdb_settings'] = {k: v for k, v in control.fetchall() if k.startswith('rocksdb_')}
            result['block_cache_bytes'] = int(result['rocksdb_settings']['rocksdb_block_cache_size'])
            if result['block_cache_bytes'] != BLOCK_CACHE_BYTES:
                raise RuntimeError('Unexpected block-cache budget')
            result['cf_options_before'] = cf_options(control)
            validate_options(result['cf_options_before'], codec)
            control.execute('SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=%s', ('engine_lab',))
            if control.fetchone()[0] != 0:
                raise RuntimeError('Fresh empty database required; refusing existing tables')
        with pymysql.connect(user='benchmark', password=os.environ['DB_PASSWORD'], **connect) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT GET_LOCK(%s,0)', (LOCK_NAME,))
                if cursor.fetchone()[0] != 1:
                    raise RuntimeError('Database busy')
                cursor.execute("SET SESSION sql_mode='STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'")
                cursor.execute('SET SESSION query_cache_type=OFF')
                result['global_variables'] = variables(cursor, 'global')
                result['session_variables'] = variables(cursor, 'session')
                cursor.execute(DDL)
                cursor.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='compression_rows'")
                result['actual_engine'] = cursor.fetchone()[0]
                if result['actual_engine'].upper() != 'ROCKSDB':
                    raise RuntimeError('Engine substitution')
                cursor.execute('SHOW CREATE TABLE compression_rows')
                result['actual_ddl'] = cursor.fetchone()[1]
                started = time.perf_counter()
                execute_seconds = 0
                for start in range(1, rows + 1, 500):
                    batch = [(i, payload(profile, i)) for i in range(start, min(start + 500, rows + 1))]
                    before = time.perf_counter()
                    cursor.executemany('INSERT INTO compression_rows (id,payload) VALUES (%s,%s)', batch)
                    execute_seconds += time.perf_counter() - before
                result['load_execute_seconds'] = execute_seconds
                result['load_with_generation_seconds'] = time.perf_counter() - started
            with admin.cursor() as control:
                before = time.perf_counter()
                control.execute('SET GLOBAL rocksdb_force_flush_memtable_now=ON')
                result['forced_flush_seconds'] = time.perf_counter() - before
                result['sst_before_reads'] = sst_snapshot(control, codec, rows)
            with connection.cursor(pymysql.cursors.SSCursor) as stream:
                result['verified_rows'] = verify_stream(stream, profile, rows, expected)
            with connection.cursor() as cursor:
                warm = query_ids(rows, round_number, config['warmups'], True)
                keys = query_ids(rows, round_number, config['lookups'])
                result['warmup_ids'] = warm
                result['lookup_ids'] = keys
                for key in warm:
                    measure(cursor, POINT, (key,), (payload(profile, key),))
                result['lookup_ms'] = [measure(cursor, POINT, (key,), (payload(profile, key),)) for key in keys]
                result['scan_ms'] = [measure(cursor, SCAN, None, (rows, expected['crc32_sum']))
                                     for _ in range(config['scans'])]
                result['plans'] = {}
                for name, statement, params in [('lookup', POINT, (keys[0],)), ('scan', SCAN, None)]:
                    cursor.execute('EXPLAIN ' + statement, params)
                    columns = [d[0] for d in cursor.description]
                    result['plans'][name] = [dict(zip(columns, r)) for r in cursor.fetchall()]
            with admin.cursor() as control:
                result['cf_options_after'] = cf_options(control)
                validate_options(result['cf_options_after'], codec)
                result['sst_after_reads'] = sst_snapshot(control, codec, rows)
                if result['sst_before_reads'] != result['sst_after_reads']:
                    raise RuntimeError('SST layout changed during reads')
                if result['cf_options_before'] != result['cf_options_after']:
                    raise RuntimeError('Column-family options changed')
    return result


def validate_trial(item, mode, identity, expected):
    config = settings(mode)
    if any(item[k] != identity[k] for k in ('profile', 'codec', 'round')):
        raise ValueError('Wrong trial identity')
    if item['mode'] != mode or item['rows'] != config['rows'] or item['verified_rows'] != config['rows']:
        raise ValueError('Wrong mode or incomplete row verification')
    if item['payload_bytes'] != PAYLOAD_BYTES or item['seed'] != SEED:
        raise ValueError('Unexpected data configuration')
    if any(item[k] != value for k, value in expected.items()):
        raise ValueError('Host/worker oracle mismatch')
    if item['actual_engine'].upper() != 'ROCKSDB' or item['block_cache_bytes'] != BLOCK_CACHE_BYTES:
        raise ValueError('Unexpected engine/cache')
    for options in ('cf_options_before', 'cf_options_after'):
        validate_options(item[options], item['codec'])
    if item['cf_options_before'] != item['cf_options_after']:
        raise ValueError('Column-family settings changed')
    for name in ('sst_before_reads', 'sst_after_reads'):
        validate_ssts(item[name], item['codec'], config['rows'])
    if item['sst_before_reads'] != item['sst_after_reads']:
        raise ValueError('SSTs changed during read measurements')
    for key, count in [('lookup_ms', config['lookups']), ('scan_ms', config['scans'])]:
        if len(item[key]) != count:
            raise ValueError('Missing query samples')
        describe(item[key])
    for key in ('load_execute_seconds', 'load_with_generation_seconds', 'forced_flush_seconds'):
        describe([item[key]])
    if item['lookup_ids'] != query_ids(config['rows'], item['round'], config['lookups']):
        raise ValueError('Unexpected measured query stream')
    if item['warmup_ids'] != query_ids(config['rows'], item['round'], config['warmups'], True):
        raise ValueError('Unexpected warmup stream')
    if item['plans']['lookup'][0]['key'] != 'PRIMARY':
        raise ValueError('Primary-key lookup plan missing')


def summary(result):
    expected_schedule = schedule(result['mode'])
    if result['status'] != 'completed' or result['schedule'] != expected_schedule or len(result['trials']) != len(expected_schedule):
        raise ValueError('Incomplete experiment')
    for item, identity in zip(result['trials'], expected_schedule):
        validate_trial(item, result['mode'], identity, result['expected_data'][identity['profile']])
        if item['position'] != identity['position'] or item['images'] != result['images']:
            raise ValueError('Trial order or image identity differs')
        if item['clean_stop'].get('ExitCode') != 0 or item['clean_stop'].get('OOMKilled') or item['clean_stop'].get('Status') != 'exited':
            raise ValueError('No verified clean shutdown')
        if item['table_sst'] != match_inventory(item['sst_after_reads'], item['sst_inventory']):
            raise ValueError('SST file totals differ from inventory')
        if item['resource_cleanup'] != {'inventory_removed': True, 'worker_removed': True, 'db_removed': True, 'volume_removed': True}:
            raise ValueError('Missing owned-resource cleanup')
    stats = {}
    for profile in PROFILES:
        stats[profile] = {}
        for codec in CODECS:
            trials = [t for t in result['trials'] if t['profile'] == profile and t['codec'] == codec]
            stats[profile][codec] = {
                'sst_bytes': describe([t['table_sst']['bytes'] for t in trials]),
                'load_execute_seconds': describe([t['load_execute_seconds'] for t in trials]),
                'forced_flush_seconds': describe([t['forced_flush_seconds'] for t in trials]),
                'lookup_ms': describe([statistics.mean(t['lookup_ms']) for t in trials]),
                'scan_ms': describe([statistics.mean(t['scan_ms']) for t in trials])
            }
    return stats


def markdown(result):
    stats = summary(result)
    def cell(value, scale=1):
        sd = value['sample_sd']
        return f"{value['mean']/scale:.4f} ± " + ('n/a' if sd is None else f'{sd/scale:.4f}')
    lines = ['# MyRocks compression: ' + result['mode'], '', 'Run: ' + result['run_id'],
             'Mean ± sample SD across trial/round means; pilot/smoke supports no ranking.',
             '', '| Data | Codec | SST MiB | Insert execute s | Forced flush s | Lookup ms | CRC32 scan ms |',
             '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for profile in PROFILES:
        for codec, values in stats[profile].items():
            lines.append('| ' + ' | '.join([profile, codec, cell(values['sst_bytes'], 1048576)] +
                         [cell(values[k]) for k in ('load_execute_seconds', 'forced_flush_seconds', 'lookup_ms', 'scan_ms')]) + ' |')
    lines += ['', 'Fresh database volume per trial; actual column-family and SST codec checked.',
              'SST bytes are table-mapped file lengths from a read-only mount after a verified clean stop.',
              'Automatic compaction is disabled in both treatments: this is a bounded flush-only study.',
              'Reads follow full row verification and warmups; timings include client/network and CRC32 work.',
              'Synthetic data, one engine and a 64 MiB full-run payload: no cold-cache, physical-SSD,',
              'steady-state compaction, server-CPU isolation or five-engine ranking claim.',
              'See docs/rocksdb-compression-method.md.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--mode', choices=('smoke', 'pilot', 'full'))
    parser.add_argument('--profile', choices=PROFILES)
    parser.add_argument('--codec', choices=CODECS)
    parser.add_argument('--round', type=int)
    args = parser.parse_args()
    if args.inventory:
        result = inventory()
    else:
        result = trial(args.mode, args.profile, args.codec, args.round)
    print(json.dumps(result, default=str))


if __name__ == '__main__':
    main()
