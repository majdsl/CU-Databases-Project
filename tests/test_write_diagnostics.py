import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmarks import write_diagnostics as b
from benchmarks.core import Config, dataset_digest, generate_rows
from benchmarks import concurrency as w
from scripts import run_write_diagnostics as host


def samples():
    before=dict(container_id='db',started_at='start',cpu_max='200000 100000',
                call_start_ns=0,call_end_ns=100000000,cpu_stat=dict(usage_usec=100,user_usec=60))
    after=dict(container_id='db',started_at='start',cpu_max='200000 100000',
               call_start_ns=2000000000,call_end_ns=2100000000,cpu_stat=dict(usage_usec=1000100,user_usec=600060))
    return before,after


def fixture(item):
    rows=generate_rows(Config(rows=100));keys=w.streams(100,100,item['clients'],item['pattern'])
    result=dict(item)
    for stage in ('prepare','writes','verify'):
        result[stage]=dict(stage=stage,mode='smoke',status='completed',**{k:item[k] for k in ('engine','pattern','clients')})
    result['prepare']['initial_dataset_sha256']=dataset_digest(rows)
    result['verify']['verified_final_sha256']=dataset_digest(w.expected_rows(rows,keys))
    lock=dict(values={k:0 for k in b.COUNTERS+b.GAUGES})
    result['writes'].update(completed=100,attempted_updates=100,elapsed_seconds=1,updates_per_second=100,
        workers=[dict(completed=len(k),latency_ms=[1]*len(k)) for k in keys],lock_before=lock,lock_after=lock,
        lock_delta=b.lock_delta(lock,lock))
    result['db_cpu']=b.server_cpu(*samples())
    return result


class WriteDiagnosticTests(unittest.TestCase):
    def test_cpu_units_and_window_bounds(self):
        cpu=b.server_cpu(*samples())
        self.assertEqual(cpu['cpu_seconds'],1)
        self.assertEqual(cpu['average_cores'],0.5)
        self.assertEqual(cpu['wall_seconds_bounds'],[1.9,2.1])

    def test_cpu_rejects_reset_restart_quota_and_missing(self):
        for field,value in [('container_id','different'),('started_at','restart'),('cpu_max','100000 100000'),
                            ('cpu_stat',{'usage_usec':0}),('cpu_stat',{})]:
            before,after=samples();after[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):b.server_cpu(before,after)

    def test_missing_lock_is_not_zero_and_gauge_can_fall(self):
        before=dict(values={'Table_locks_waited':10,'Innodb_row_lock_current_waits':2})
        after=dict(values={'Table_locks_waited':13,'Innodb_row_lock_current_waits':0})
        delta=b.lock_delta(before,after)
        self.assertEqual(delta['Table_locks_waited'],3)
        self.assertIsNone(delta['Innodb_row_lock_waits'])
        after['values']['Table_locks_waited']=9
        with self.assertRaises(ValueError):b.lock_delta(before,after)

    def test_full_schedule_balances_engine_position_and_fixed_work(self):
        schedule=b.schedule('full');self.assertEqual(len(schedule),150)
        for engine in b.ENGINES:
            positions=[]
            for r in range(1,6):
                order=list(dict.fromkeys(t['engine'] for t in schedule if t['round']==r))
                positions.append(order.index(engine))
            self.assertEqual(sorted(positions),list(range(5)))
        for item in schedule:
            keys=w.streams(10000,10000,item['clients'],item['pattern'])
            self.assertEqual(sum(map(len,keys)),10000)

    def test_host_validation_detects_wrong_data_workers_and_cpu(self):
        item=b.schedule('smoke')[0];original=fixture(item)
        b.validate_trial(original,'smoke',item)
        for path,value in [(('verify','verified_final_sha256'),'bad'),(('writes','completed'),99),
                           (('writes','workers'),[]),(('db_cpu','average_cores'),5)]:
            trial=copy.deepcopy(original);trial[path[0]][path[1]]=value
            with self.subTest(path=path),self.assertRaises(ValueError):b.validate_trial(trial,'smoke',item)

    def test_report_rejects_partial_and_duplicates(self):
        schedule=b.schedule('smoke')
        result=dict(mode='smoke',status='completed',trials=[fixture(t) for t in schedule])
        self.assertIn('not applicable',b.summary(result))
        result['trials'][-1]=result['trials'][0]
        with self.assertRaises(ValueError):b.summary(result)
        result['trials'].pop()
        with self.assertRaises(ValueError):b.summary(result)

    def test_worker_requires_isolation_before_connecting(self):
        with patch.dict(os.environ,{},clear=True),patch.object(w,'connect') as connection:
            with self.assertRaises(ValueError):b.worker('prepare','smoke','InnoDB',1,'disjoint')
            connection.assert_not_called()

    def test_normal_project_and_existing_resources_rejected(self):
        with patch.object(host,'execute') as execute:
            with self.assertRaises(ValueError):host.compose('cu-engine-lab','down','--volumes')
            execute.assert_not_called()
            execute.return_value='existing'
            with self.assertRaises(RuntimeError):host.ensure_new('cu-writes-'+'a'*32+'-1')

    def test_failed_worker_retains_volume_and_partial_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'.env').touch()
            for name in ('scripts/run_write_diagnostics.py','compose.write-diagnostics.yaml','benchmarks/write_diagnostics.py'):
                target=root/name;target.parent.mkdir(parents=True,exist_ok=True);target.touch()
            calls=[]
            def compose(project,*args,**kwargs):
                calls.append(args);return ''
            with patch.object(host,'ROOT',root),patch.object(host,'execute',return_value='linux/amd64'),\
                 patch.object(host,'ensure_new'),patch.object(host,'compose',side_effect=compose),\
                 patch.object(host,'identity',return_value={'Image':'image','Id':'db','State':{'StartedAt':'start'}}),\
                 patch.object(host,'cpu_sample',side_effect=list(samples())),\
                 patch.object(host,'stage',side_effect=[{'status':'completed'},{'status':'failed'}]):
                with self.assertRaises(RuntimeError):host.run('smoke','test')
            self.assertFalse(any('down' in args for args in calls))
            self.assertTrue(any('stop' in args for args in calls))
            results=list((root/'results').glob('*/results.json'))
            saved=json.loads(results[0].read_text())
            self.assertEqual(saved['status'],'failed')
            self.assertEqual(saved['trials'][0]['writes']['status'],'failed')
            self.assertFalse((results[0].parent/'summary.md').exists())


if __name__=='__main__':unittest.main()
