import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from benchmarks import openflights as bench
from benchmarks import openflights_data as data
from benchmarks.core import ENGINES, dataset_digest, engine_schedule

RAW = b'2B,410,AER,2965,KZN,2990,,0,CR2\nXX,\\N,AAA,\\N,BBB,\\N,Y,1,"CR2 320"\n2B,410,AER,2965,KZN,2990,,0,320\n'


class Cursor:
    """In-memory SQL protocol double, not a claim of real engine validation."""
    def __init__(self, connection):
        self.connection = connection; self.answer = []; self.pending = []

    def __enter__(self): return self
    def __exit__(self, *args): return False

    def execute(self, sql, params=None):
        c = self.connection; c.statements.append(sql); self.answer = []
        if sql.startswith('SELECT GET_LOCK'): self.answer = [(1,)]
        elif sql == 'SELECT VERSION()': self.answer = [('11.8.9-MariaDB',)]
        elif sql == 'SHOW ENGINES': self.answer = [(e, 'YES') for e in ENGINES]
        elif sql.startswith('SHOW GLOBAL') or sql.startswith('SHOW SESSION'): self.answer = [('autocommit', 'ON')]
        elif sql.startswith('SELECT TABLE_NAME'): self.answer = [('openflights_routes',)] if c.exists else []
        elif sql.startswith('CREATE TABLE'):
            c.exists = True; c.engine = sql.split('ENGINE=')[1].split()[0]; c.rows = []
        elif sql.startswith('SELECT ENGINE'): self.answer = [(c.substitution or c.engine,)]
        elif sql.startswith('SHOW CREATE'): self.answer = [('openflights_routes', bench.ddl(c.engine))]
        elif sql.startswith('ANALYZE'): self.answer = [('engine_lab.openflights_routes', 'analyze', 'status', 'OK')]
        elif sql == bench.SELECT_ALL:
            self.pending = list(c.rows)
            if c.corrupt: self.pending = self.pending[:-1]
        elif sql == bench.POINT: self.answer = [c.rows[params[0]-1]]
        elif sql == bench.SCAN: self.answer = [bench.oracles(c.rows)[0]]
        elif sql == bench.SOURCE: self.answer = [bench.oracles(c.rows)[1][params[0]]]
        elif sql.startswith('EXPLAIN'): self.answer = [('plan',)]
        elif sql.startswith('DROP TABLE'): c.exists = False; c.drops += 1

    def executemany(self, sql, rows):
        if self.connection.insert_error: raise RuntimeError('insert failed')
        self.connection.rows.extend(rows)

    def fetchone(self): return self.answer.pop(0) if self.answer else None
    def fetchall(self): return self.answer
    def fetchmany(self, count):
        batch = self.pending[:count]; self.pending = self.pending[count:]; return batch


class Connection:
    def __init__(self, exists=False, substitution=None, corrupt=False, insert_error=False):
        self.exists = exists; self.substitution = substitution; self.corrupt = corrupt
        self.insert_error = insert_error; self.statements = []; self.rows = []; self.drops = 0
    def cursor(self): return Cursor(self)
    def __enter__(self): return self
    def __exit__(self, *args): return False


class OpenFlightsTests(unittest.TestCase):
    def setUp(self):
        self.rows = data.parse_routes(RAW)
        self.config = bench.Config(pilot=True, lookups=10, scans=2, source_queries=10)
        self.manifest = dict(schema_version=1, sha256=hashlib.sha256(RAW).hexdigest(),
            bytes=len(RAW), rows=3, commit='a'*40,
            url='https://raw.githubusercontent.com/MariaDB/openflights/'+'a'*40+'/data/routes.dat')

    def fixture_directory(self, directory):
        (directory/'manifest.json').write_text(json.dumps(self.manifest))

    def test_parser_preserves_nulls_empty_strings_and_repeated_route_keys(self):
        self.assertEqual(len(self.rows), 3)
        self.assertEqual(self.rows[1], (2, 'XX', None, 'AAA', None, 'BBB', None, 'Y', 1, 'CR2 320'))
        self.assertEqual(self.rows[0][7], '')
        self.assertEqual(self.rows[0][2:7], self.rows[2][2:7])
        self.assertNotEqual(self.rows[0][0], self.rows[2][0])

    def test_parser_rejects_malformed_rows_and_truncation(self):
        for raw in [b'', b'1,2\n', RAW.replace(b'410', b'-1'), RAW.replace(b',0,', b',256,'),
                    RAW.replace(b'2B,', b'TOOLONG,'), RAW.replace(b'CR2\n', b'X'*65+b'\n')]:
            with self.subTest(raw=raw), self.assertRaises(ValueError): data.parse_routes(raw)

    def test_checksum_and_row_count_are_required(self):
        self.assertEqual(data.validate_bytes(RAW, self.manifest), self.rows)
        for raw, manifest in [(RAW+b'\n', self.manifest),
                              (RAW.replace(b'CR2', b'CR3'), self.manifest),
                              (RAW, dict(self.manifest, rows=4))]:
            with self.assertRaises(ValueError): data.validate_bytes(raw, manifest)

    def test_existing_bad_download_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'urlopen') as fetch:
            directory = Path(tmp); self.fixture_directory(directory)
            (directory/'routes.dat').write_bytes(b'bad')
            with self.assertRaises(ValueError): data.fetch_dataset(directory)
            fetch.assert_not_called(); self.assertEqual((directory/'routes.dat').read_bytes(), b'bad')

    def test_bad_network_payload_never_becomes_dataset(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'urlopen') as fetch:
            directory = Path(tmp); self.fixture_directory(directory)
            fetch.return_value.__enter__.return_value.read.return_value = b'bad'
            with self.assertRaises(ValueError): data.fetch_dataset(directory)
            self.assertFalse((directory/'routes.dat').exists())

    def test_verified_download_and_offline_reuse(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(data, 'urlopen') as fetch:
            directory = Path(tmp); self.fixture_directory(directory)
            fetch.return_value.__enter__.return_value.read.return_value = RAW
            data.fetch_dataset(directory); data.fetch_dataset(directory)
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(data.load_dataset(directory)[1], self.rows)

    def test_schema_is_identical_except_engine_and_uses_btree(self):
        normalized = [bench.ddl(e).replace('ENGINE='+e, 'ENGINE=ENGINE') for e in ENGINES]
        self.assertEqual(len(set(normalized)), 1)
        self.assertEqual(normalized[0].count('USING BTREE'), 2)
        self.assertNotIn('UNIQUE KEY', normalized[0])
        with self.assertRaises(ValueError): bench.ddl('InnoDB; DROP TABLE x')

    def test_oracles_include_nulls_and_nonindexed_row_values(self):
        scan, sources = bench.oracles(self.rows)
        self.assertEqual(scan, (3, 1, 13))
        self.assertEqual(sources, {2965: (2, 0)})
        self.assertEqual(bench.query_streams(self.config, 0, self.rows, sources),
                         bench.query_streams(self.config, 0, self.rows, sources))

    def test_verification_detects_changed_missing_extra_and_reordered_rows(self):
        for actual in [self.rows[:-1], self.rows+[self.rows[0]], list(reversed(self.rows)),
                       [tuple([99]+list(self.rows[0][1:]))]+self.rows[1:]]:
            cursor = MagicMock(); cursor.fetchmany.side_effect = [actual, []]
            with self.assertRaises(RuntimeError): bench.verify_rows(cursor, self.rows)

    def perform_trial(self, connection):
        return bench.trial(connection, 'InnoDB', self.config, self.rows, 0, *bench.oracles(self.rows))

    def test_existing_table_is_not_changed(self):
        connection = Connection(exists=True)
        with self.assertRaises(RuntimeError): self.perform_trial(connection)
        self.assertEqual(len(connection.statements), 1); self.assertEqual(connection.drops, 0)

    def test_substitution_and_failed_writes_preserve_trial_table(self):
        for connection in [Connection(substitution='Aria'), Connection(insert_error=True), Connection(corrupt=True)]:
            with self.assertRaises(RuntimeError): self.perform_trial(connection)
            self.assertTrue(connection.exists); self.assertEqual(connection.drops, 0)

    def test_successful_trial_checks_data_and_cleans_only_owned_table(self):
        connection = Connection(); result = self.perform_trial(connection)
        self.assertEqual(result['verified_dataset_sha256'], dataset_digest(self.rows))
        self.assertEqual(result['verified_rows'], 3); self.assertEqual(connection.drops, 1)
        self.assertEqual(len(result['lookup_ms']), 10); self.assertEqual(len(result['source_ms']), 10)

    def result_fixture(self):
        config = bench.Config(lookups=10, scans=2, source_queries=10)
        result = dict(config=bench.asdict(config), status='completed', rows=3,
            schedule=engine_schedule(config.seed, 5), dataset_sha256=dataset_digest(self.rows), trials=[])
        for r, engines in enumerate(result['schedule'], 1):
            for p, engine in enumerate(engines, 1):
                result['trials'].append(dict(engine=engine, round=r, position=p, verified_rows=3,
                    verified_dataset_sha256=result['dataset_sha256'], load_seconds=r,
                    lookup_ms=[r]*10, scan_ms=[r]*2, source_ms=[r]*10))
        return result

    def test_statistics_use_five_round_means(self):
        stats = bench.summarize(self.result_fixture())
        self.assertEqual(stats['InnoDB']['lookup_ms']['n'], 5)
        self.assertEqual(stats['InnoDB']['lookup_ms']['mean'], 3)

    def test_incomplete_invalid_or_unverified_runs_cannot_be_summarized(self):
        valid = self.result_fixture()
        for change in [lambda r:r.update(status='failed'), lambda r:r['trials'].pop(),
                       lambda r:r['trials'][0].update(verified_rows=2),
                       lambda r:r['trials'][0]['lookup_ms'].pop(),
                       lambda r:r['trials'][0]['scan_ms'].__setitem__(0, float('nan'))]:
            result = copy.deepcopy(valid); change(result)
            with self.assertRaises(ValueError): bench.summarize(result)

    def test_invalid_config_and_database_rejected_before_loading(self):
        with self.assertRaises(ValueError): bench.Config(lookups=0).validate()
        with patch.dict(os.environ, {'DB_NAME': 'production'}), patch.object(bench, 'load_dataset') as load:
            with self.assertRaises(ValueError): bench.run(self.config, Path('/unused'), 'plugged in')
            load.assert_not_called()

    def test_connection_failure_leaves_failed_checkpoint_without_summary(self):
        connector = types.SimpleNamespace(connect=MagicMock(side_effect=RuntimeError('offline')))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys_modules(), {'pymysql': connector}), \
             patch.dict(os.environ, {'DB_NAME': 'engine_lab', 'DB_HOST': 'db', 'DB_USER': 'u', 'DB_PASSWORD': 'p'}), \
             patch.object(bench, 'load_dataset', return_value=(self.manifest, self.rows)), \
             patch.object(bench, 'runtime_metadata', return_value={}):
            with self.assertRaises(RuntimeError): bench.run(self.config, Path(tmp), 'test')
            paths = list(Path(tmp).glob('*/results.json')); self.assertEqual(len(paths), 1)
            self.assertEqual(json.loads(paths[0].read_text())['status'], 'failed')
            self.assertFalse(paths[0].with_name('summary.md').exists())

    def test_complete_pilot_checkpoint_and_summary(self):
        connection = Connection(); connector = types.SimpleNamespace(connect=MagicMock(return_value=connection))
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys_modules(), {'pymysql': connector}), \
             patch.dict(os.environ, {'DB_NAME': 'engine_lab', 'DB_HOST': 'db', 'DB_USER': 'u', 'DB_PASSWORD': 'p'}), \
             patch.object(bench, 'load_dataset', return_value=(self.manifest, self.rows)), \
             patch.object(bench, 'runtime_metadata', return_value={}):
            bench.run(self.config, Path(tmp), 'test')
            path = next(Path(tmp).glob('*/results.json')); result = json.loads(path.read_text())
            self.assertEqual(result['status'], 'completed'); self.assertEqual(len(result['trials']), 5)
            self.assertEqual(connection.drops, 5); self.assertNotIn('active_trial', result)
            self.assertIn('PILOT', path.with_name('summary.md').read_text())


def sys_modules():
    import sys
    return sys.modules


if __name__ == '__main__': unittest.main()
