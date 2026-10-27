import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from benchmarks import rocksdb_compression as b
from scripts import run_rocksdb_compression as host


def cf(codec):
    return dict(COMPRESSION_TYPE=b.CODECS[codec], BOTTOMMOST_COMPRESSION=b.CODECS[codec],
                COMPRESSION_PER_LEVEL='NUL', WRITE_BUFFER_SIZE=str(b.WRITE_BUFFER_BYTES),
                DISABLE_AUTO_COMPACTIONS='true')


def fixture(identity):
    config = b.settings('smoke')
    codec = identity['codec']
    ssts = [dict(SST_NAME='000021.sst', COMPRESSION_ALGO='NoCompression' if codec == 'none' else 'ZSTD',
                 ENTRIES=config['rows'])]
    result = dict(identity, mode='smoke', rows=config['rows'], verified_rows=config['rows'],
        payload_bytes=b.PAYLOAD_BYTES, seed=b.SEED, actual_engine='ROCKSDB',
        block_cache_bytes=b.BLOCK_CACHE_BYTES, cf_options_before=cf(codec), cf_options_after=cf(codec),
        sst_before_reads=ssts, sst_after_reads=copy.deepcopy(ssts),
        lookup_ms=[1.0] * config['lookups'], scan_ms=[2.0] * config['scans'],
        load_execute_seconds=0.5, load_with_generation_seconds=0.6, forced_flush_seconds=0.1,
        lookup_ids=b.query_ids(config['rows'], identity['round'], config['lookups']),
        warmup_ids=b.query_ids(config['rows'], identity['round'], config['warmups'], True),
        plans={'lookup': [{'key': 'PRIMARY'}]}, **b.oracle(identity['profile'], config['rows']))
    return result


def owned_info(resources, role='db'):
    exp = resources.experiment
    mount = dict(Type='volume', Name=resources.volume, Destination='/var/lib/mysql', RW=True)
    return dict(Id=resources.containers[role], Name='/' + resources.name(role), Image=exp.images['db']['id'],
        Config={'Labels': dict(resources.labels)}, Mounts=[mount],
        HostConfig={'NetworkMode': 'none', 'PortBindings': {}, 'Memory': 2 * 1024**3, 'NanoCpus': 2000000000},
        State={'Status': 'exited', 'ExitCode': 0, 'OOMKilled': False})


class RocksDBCompressionTests(unittest.TestCase):
    def test_full_design_balances_position_and_every_pair_order(self):
        schedule = b.schedule('full')
        self.assertEqual(len(schedule), 32)
        conditions = b.CONDITIONS
        for condition in conditions:
            positions = [x['position'] for x in schedule if (x['profile'], x['codec']) == condition]
            self.assertEqual([positions.count(i) for i in range(1, 5)], [2, 2, 2, 2])
        for first in range(4):
            for second in range(first + 1, 4):
                before = 0
                for r in range(1, 9):
                    block = [(x['profile'], x['codec']) for x in schedule if x['round'] == r]
                    before += block.index(conditions[first]) < block.index(conditions[second])
                self.assertEqual(before, 4)

    def test_stream_rejects_corruption_missing_extra_and_reordered_rows(self):
        for profile in b.PROFILES:
            rows = [(i, b.payload(profile, i)) for i in range(1, 4)]
            expected = b.oracle(profile, 3)
            cursor = MagicMock()
            cursor.fetchmany.side_effect = [rows, []]
            self.assertEqual(b.verify_stream(cursor, profile, 3, expected), 3)
            for altered in [rows[:-1], rows + [(4, b.payload(profile, 4))], rows[::-1], [(1, b'bad')] + rows[1:]]:
                cursor = MagicMock()
                cursor.fetchmany.side_effect = [altered, []]
                with self.assertRaises(RuntimeError):
                    b.verify_stream(cursor, profile, 3, expected)

    def test_option_fallback_and_compaction_overrides_are_rejected(self):
        b.validate_options(cf('zstd'), 'zstd')
        for field, value in [('COMPRESSION_TYPE', 'kSnappyCompression'),
                             ('BOTTOMMOST_COMPRESSION', 'kDisableCompressionOption'),
                             ('COMPRESSION_PER_LEVEL', 'kNoCompression:kZSTD'),
                             ('WRITE_BUFFER_SIZE', '1'), ('DISABLE_AUTO_COMPACTIONS', 'false')]:
            changed = cf('zstd')
            changed[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                b.validate_options(changed, 'zstd')

    def test_missing_wrong_duplicate_and_incomplete_sst_properties_rejected(self):
        valid = [dict(SST_NAME='000001.sst', COMPRESSION_ALGO='ZSTD', ENTRIES=3)]
        b.validate_ssts(valid, 'zstd', 3)
        for bad in [[], valid * 2, [dict(valid[0], ENTRIES=2)],
                    [dict(valid[0], SST_NAME='../000001.sst')],
                    [dict(valid[0], COMPRESSION_ALGO='Snappy')]]:
            with self.assertRaises(ValueError):
                b.validate_ssts(bad, 'zstd', 3)

    def test_inventory_requires_each_mapped_file_once_and_nonzero(self):
        ssts = [dict(SST_NAME='000001.sst')]
        files = [dict(name='000001.sst', bytes=123, allocated_bytes=4096),
                 dict(name='000002.sst', bytes=99, allocated_bytes=4096)]
        self.assertEqual(b.match_inventory(ssts, files)['bytes'], 123)
        for altered in [[], files * 2, [dict(files[0], bytes=0)]]:
            with self.assertRaises(ValueError):
                b.match_inventory(ssts, altered)

    @unittest.skipIf(os.name != 'posix', 'Filesystem inventory runs inside Linux Docker')
    def test_inventory_rejects_symlinks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            directory = root / '#rocksdb'
            directory.mkdir()
            (directory / '000001.sst').write_bytes(b'123')
            self.assertEqual(b.inventory(root)[0]['bytes'], 3)
            (directory / '000002.sst').symlink_to(directory / '000001.sst')
            with self.assertRaises(RuntimeError):
                b.inventory(root)

    def test_worker_refuses_nonisolated_environment_before_connection(self):
        with patch.dict(os.environ, {'COMPRESSION_EXPERIMENT': '', 'DB_NAME': 'engine_lab', 'DB_HOST': '127.0.0.1'}):
            with self.assertRaises(ValueError):
                b.trial('smoke', 'random', 'none', 1)

    def test_nonfinite_and_incomplete_query_samples_rejected(self):
        identity = b.schedule('smoke')[0]
        original = fixture(identity)
        for key, value in [('lookup_ms', [float('nan')] * b.settings('smoke')['lookups']),
                           ('scan_ms', []), ('dataset_sha256', 'wrong')]:
            trial = copy.deepcopy(original)
            trial[key] = value
            with self.assertRaises(ValueError):
                b.validate_trial(trial, 'smoke', identity, b.oracle(identity['profile'], trial['rows']))

    def test_existing_resources_and_invalid_names_are_never_reused(self):
        exp = host.Experiment('smoke', 'test')
        exp.call = MagicMock(return_value='existing')
        resources = host.TrialResources(exp, 1)
        with self.assertRaises(RuntimeError):
            resources.ensure_new()
        self.assertFalse(any('create' in call.args[0] for call in exp.call.call_args_list))
        exp.token = 'normal-lab'
        with self.assertRaises(ValueError):
            host.TrialResources(exp, 1)

    def test_foreign_image_labels_mounts_and_quotas_refused_before_mutation(self):
        exp = host.Experiment('smoke', 'test')
        exp.images = {'db': {'id': 'sha256:' + 'a' * 64}}
        resources = host.TrialResources(exp, 1)
        resources.containers['db'] = 'b' * 64
        original = owned_info(resources)
        cases = []
        foreign = copy.deepcopy(original)
        foreign['Config']['Labels']['cu.compression.owner'] = 'foreign'
        cases.append(foreign)
        changed = copy.deepcopy(original); changed['Image'] = 'sha256:' + 'c' * 64; cases.append(changed)
        changed = copy.deepcopy(original); changed['Mounts'][0]['Name'] = 'production_data'; cases.append(changed)
        changed = copy.deepcopy(original); changed['HostConfig']['NanoCpus'] = 4000000000; cases.append(changed)
        changed = copy.deepcopy(original); changed['HostConfig']['NetworkMode'] = 'host'; cases.append(changed)
        for info in cases:
            exp.call = MagicMock(return_value=json.dumps([info]))
            with self.assertRaises(RuntimeError):
                resources.identity('db')
            self.assertFalse(any('rm' in call.args[0] or 'stop' in call.args[0] for call in exp.call.call_args_list))

    def test_live_database_cannot_be_inventoried_or_deleted(self):
        exp = host.Experiment('smoke', 'test')
        resources = host.TrialResources(exp, 1)
        with patch.object(resources, 'identity', return_value={'State': {'Status': 'running'}}), patch.object(resources, 'create') as create:
            with self.assertRaises(RuntimeError):
                resources.read_inventory()
            create.assert_not_called()

    def test_private_inspection_credentials_and_local_paths_not_logged(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = host.Experiment('smoke', 'test')
            exp.directory = Path(tmp)
            password = exp.credentials['MARIADB_ROOT_PASSWORD']
            response = MagicMock(returncode=0, stdout='private ' + password, stderr=password + ' ' + str(host.ROOT))
            with patch.object(host.subprocess, 'run', return_value=response):
                exp.call(['docker', 'container', 'inspect', 'owned'], private=True)
            text = json.dumps(exp.commands)
            self.assertNotIn(password, text)
            self.assertNotIn(str(host.ROOT), text)
            self.assertNotIn('private ' + password, text)
            self.assertIn('[private output omitted]', text)

    def test_remote_context_rejected_before_any_creation(self):
        exp = host.Experiment('smoke', 'test')
        exp.call = MagicMock(side_effect=[
            json.dumps({'os': 'linux', 'architecture': 'amd64'}),
            'remote', json.dumps('tcp://remote.invalid:2376')])
        with patch.object(host.platform, 'machine', return_value='x86_64'), patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                exp.preflight()
        self.assertFalse(any('create' in call.args[0] for call in exp.call.call_args_list))

    def test_stale_or_missing_worker_fingerprint_rejected(self):
        exp = host.Experiment('smoke', 'test')
        exp.result['source_sha256'] = {'benchmarks/rocksdb_compression.py': 'expected'}
        exp.verify_worker_source({'source_sha256': {'benchmarks/rocksdb_compression.py': 'expected'}})
        for recorded in [{}, {'benchmarks/rocksdb_compression.py': 'stale'}]:
            with self.assertRaises(RuntimeError):
                exp.verify_worker_source({'source_sha256': recorded})

    def test_failed_start_retains_resources_and_failed_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            exp = host.Experiment('smoke', 'test')
            exp.directory = Path(tmp) / 'run'
            with patch.object(exp, 'preflight'), patch.object(exp, 'build_images'), \
                 patch.object(host.TrialResources, 'ensure_new'), \
                 patch.object(host.TrialResources, 'start_database', side_effect=RuntimeError('failed startup')), \
                 patch.object(host.TrialResources, 'retain_on_failure', return_value={'db': 'retained'}), \
                 patch.object(host.TrialResources, 'cleanup') as cleanup:
                with self.assertRaises(RuntimeError):
                    exp.run()
            saved = json.loads((exp.directory / 'results.json').read_text())
            self.assertEqual(saved['status'], 'failed')
            self.assertIn('retained_project', saved)
            self.assertFalse((exp.directory / 'summary.md').exists())
            cleanup.assert_not_called()

    def test_partial_runs_cannot_be_summarized(self):
        for status in ('failed', 'completed'):
            with self.assertRaises(ValueError):
                b.summary(dict(mode='full', status=status, schedule=b.schedule('full'), trials=[]))

    def test_completed_run_requires_clean_stop_inventory_and_exact_images(self):
        images = {'db': {'id': 'db'}, 'runner': {'id': 'runner'}}
        result = dict(mode='smoke', status='completed', schedule=b.schedule('smoke'), images=images,
                      expected_data={p: b.oracle(p, b.settings('smoke')['rows']) for p in b.PROFILES}, trials=[])
        for identity in result['schedule']:
            item = fixture(identity)
            item.update(images=copy.deepcopy(images), clean_stop=dict(Status='exited', ExitCode=0, OOMKilled=False),
                        sst_inventory=[dict(name='000021.sst', bytes=100, allocated_bytes=4096)],
                        resource_cleanup=dict(inventory_removed=True, worker_removed=True, db_removed=True, volume_removed=True))
            item['table_sst'] = b.match_inventory(item['sst_after_reads'], item['sst_inventory'])
            result['trials'].append(item)
        self.assertEqual(b.summary(result)['random']['zstd']['sst_bytes']['mean'], 100)
        for key, value in [('images', {'db': {'id': 'different'}}),
                           ('clean_stop', dict(Status='exited', ExitCode=137, OOMKilled=False)),
                           ('table_sst', {'bytes': 101}), ('resource_cleanup', {})]:
            changed = copy.deepcopy(result)
            changed['trials'][0][key] = value
            with self.assertRaises(ValueError):
                b.summary(changed)


if __name__ == '__main__':
    unittest.main()
