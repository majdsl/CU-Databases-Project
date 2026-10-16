import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from benchmarks import cache_pressure as b
from scripts import run_cache_pressure as host


class CachePressureTests(unittest.TestCase):
    def test_full_schedule_balances_size_order(self):
        s=b.schedule('full');self.assertEqual(len(s),12)
        for size in b.settings('full')['sizes']:
            positions=[x['position'] for x in s if x['rows']==size]
            self.assertEqual(positions.count(1),3);self.assertEqual(positions.count(2),3)

    def test_payload_and_host_oracle_are_reproducible(self):
        self.assertEqual(len(b.payload(1)),1024)
        self.assertEqual(b.payload(1),b.payload(1));self.assertNotEqual(b.payload(1),b.payload(2))
        self.assertEqual(host.expected_data(3),host.expected_data(3))
        self.assertNotEqual(host.expected_data(3),host.expected_data(4))

    def test_stream_verification_rejects_corruption_missing_extra(self):
        digest=host.expected_data(3)['dataset_sha256'];rows=[(i,b.payload(i)) for i in range(1,4)]
        cur=MagicMock();cur.fetchmany.side_effect=[rows,[]]
        self.assertEqual(b.verify_stream(cur,3,digest),host.expected_data(3)['crc32_sum'])
        for data in (rows[:-1],rows+[(4,b.payload(4))],[(1,b'wrong')]+rows[1:],rows[::-1]):
            cur=MagicMock();cur.fetchmany.side_effect=[data,[]]
            with self.assertRaises(RuntimeError):b.verify_stream(cur,3,digest)

    def test_actual_footprint_required(self):
        b.check_footprint('pilot',32768,50*1048576,b.POOL)
        b.check_footprint('pilot',262144,300*1048576,b.POOL)
        for rows,allocated,pool in [(32768,b.POOL,b.POOL),(262144,64*1048576,b.POOL),(32768,50*1048576,64*1048576)]:
            with self.assertRaises(RuntimeError):b.check_footprint('pilot',rows,allocated,pool)

    def test_counter_resets_rejected_but_gauges_can_decrease(self):
        before={k:10 for k in b.COUNTERS+b.GAUGES};after={k:11 for k in b.COUNTERS+b.GAUGES}
        after[b.GAUGES[0]]=0
        self.assertTrue(all(x==1 for x in b.delta(before,after).values()))
        after[b.COUNTERS[0]]=0
        with self.assertRaises(RuntimeError):b.delta(before,after)

    def test_missing_counters_not_zero(self):
        cursor=MagicMock();cursor.fetchall.return_value=[]
        with self.assertRaises(RuntimeError):b.snapshot(cursor)

    def test_worker_requires_isolation_before_connection(self):
        with patch.dict(os.environ,{'DB_NAME':'engine_lab','CACHE_PRESSURE_EXPERIMENT':''}):
            with self.assertRaises(ValueError):b.one_trial('smoke',128,1)

    def test_host_refuses_normal_or_preexisting_project(self):
        with patch.object(host,'execute') as execute:
            with self.assertRaises(ValueError):host.compose('cu-engine-lab','down','--volumes')
            execute.assert_not_called()
        with patch.object(host,'execute',return_value='existing'):
            with self.assertRaises(RuntimeError):host.ensure_new('cu-pressure-'+'a'*32+'-1')

    def test_unclean_shutdown_prevents_successful_cleanup(self):
        with patch.object(host,'compose'),patch.object(host,'identity',return_value={'State':{'Status':'exited','ExitCode':137,'OOMKilled':False}}):
            with self.assertRaises(RuntimeError):host.stop_cleanly('cu-pressure-'+'a'*32+'-1')

    def test_failed_start_preserves_project_and_checkpoint(self):
        calls=[]
        def compose(project,*args,**kwargs):
            calls.append(args)
            if args[0]=='up':raise RuntimeError('failed startup')
            return ''
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'.env').write_text('test fixture')
            for f in ['scripts/run_cache_pressure.py','compose.cache-pressure.yaml','benchmarks/cache_pressure.py']:
                p=root/f;p.parent.mkdir(exist_ok=True);p.write_text('fixture')
            with patch.object(host,'ROOT',root),patch.object(host,'execute',side_effect=lambda argv,capture=False:'linux/amd64' if argv[1]=='info' else 'vtest'),patch.object(host,'ensure_new'),patch.object(host,'compose',side_effect=compose):
                with self.assertRaises(RuntimeError):host.run('smoke','test')
            result=json.loads(next(root.glob('results/*/results.json')).read_text())
            self.assertEqual(result['status'],'failed');self.assertIn('active_project',result)
            self.assertFalse(any(a[0]=='down' for a in calls))
            self.assertTrue(any(a[0]=='stop' for a in calls))
            self.assertFalse(list(root.glob('results/*/summary.md')))

    def test_incomplete_runs_cannot_be_summarized(self):
        for status in ('failed','completed'):
            with self.assertRaises(ValueError):b.summary({'mode':'full','status':status,'schedule':b.schedule('full'),'trials':[]})

    def test_queries_verify_payload_and_crc(self):
        cur=MagicMock();cur.fetchone.return_value=(b.payload(2),)
        with self.assertRaises(RuntimeError):b.query(cur,b.POINT,(1,),(b.payload(1),))
        cur.fetchone.return_value=(3,999)
        with self.assertRaises(RuntimeError):b.query(cur,b.SCAN,None,(3,host.expected_data(3)['crc32_sum']))


if __name__=='__main__':unittest.main()
