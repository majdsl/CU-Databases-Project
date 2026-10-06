import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from benchmarks import recovery

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('recovery_host',ROOT/'scripts/run_recovery.py')
host=importlib.util.module_from_spec(spec);spec.loader.exec_module(host)
PROJECT='cu-recovery-'+'a'*32+'-1'


def owned_info(running=True,exit_code=0):
    return dict(labels={'com.docker.compose.project':PROJECT,'com.docker.compose.service':'db'},
        mounts=[{'Type':'volume','Name':PROJECT+'_recovery_data','Destination':'/var/lib/mysql'}],
        state={'Running':running,'Status':'running' if running else 'exited','ExitCode':exit_code,'OOMKilled':False},image_id='image')


class RecoveryTests(unittest.TestCase):
    def test_guard_rejects_normal_database(self):
        with patch.dict(os.environ,{'DB_NAME':'engine_lab'},clear=True), self.assertRaises(ValueError):
            recovery.guard()

    def test_row_limits(self):
        for count in (True,99,10001):
            with self.assertRaises(ValueError): recovery.make_rows(count,1)

    def test_compare_intact_missing_changed_unexpected_and_duplicates(self):
        rows=recovery.make_rows(100,1)
        self.assertTrue(recovery.compare_rows(rows,rows)['exact_match'])
        actual=list(rows[1:]); actual[0]=tuple(list(actual[0][:-1])+['wrong'])
        actual += [(101,*rows[0][1:]),rows[5]]
        result=recovery.compare_rows(rows,actual)
        self.assertFalse(result['exact_match']);self.assertEqual(result['missing_ids'],[1])
        self.assertEqual(result['changed_ids'],[2]);self.assertEqual(result['unexpected_ids'],[101])
        self.assertEqual(result['duplicate_ids'],[6])

    def test_empty_is_readable_loss_not_unavailable(self):
        result=recovery.compare_rows(recovery.make_rows(100,1),[])
        self.assertEqual(result['status'],'readable');self.assertEqual(len(result['missing_ids']),100)
        self.assertTrue(host.ordinary_outcome('MEMORY',result))
        self.assertFalse(host.ordinary_outcome('InnoDB',result))
        self.assertFalse(host.ordinary_outcome('MEMORY',{'status':'unreadable'}))

    def test_inserts_not_retried_after_ambiguous_failure(self):
        cursor=MagicMock();cursor.rowcount=1;cursor.execute.side_effect=[None,ConnectionError('lost')]
        with self.assertRaises(ConnectionError): recovery.insert_acknowledged(cursor,recovery.make_rows(100,1))
        self.assertEqual(cursor.execute.call_count,2)

    def test_each_ack_follows_a_single_row_success(self):
        cursor=MagicMock();cursor.rowcount=1
        self.assertEqual(recovery.insert_acknowledged(cursor,recovery.make_rows(100,1)),list(range(1,101)))
        self.assertEqual(cursor.execute.call_count,100)
        cursor.rowcount=0
        with self.assertRaises(RuntimeError): recovery.insert_acknowledged(cursor,recovery.make_rows(100,1))

    def test_atomic_receipt_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'acknowledgments.json';recovery.save_receipt(p,{'acknowledged_count':100})
            self.assertEqual(json.loads(p.read_text())['acknowledged_count'],100)
            self.assertFalse(p.with_suffix('.tmp').exists())
            with self.assertRaises(RuntimeError): recovery.save_receipt(p,{'changed':True})

    def test_prepare_refuses_preexisting_tables_before_ddl(self):
        connection=MagicMock();cursor=connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.return_value=(1,);cursor.fetchall.return_value=[('user_data',)]
        with patch.object(recovery,'guard'),patch.object(recovery,'connect',return_value=connection):
            with self.assertRaisesRegex(RuntimeError,'nonempty'):
                recovery.prepare('InnoDB',100,1,Path('/unused'))
        self.assertFalse(any(any(word in c.args[0] for word in ('CREATE','DROP','INSERT')) for c in cursor.execute.call_args_list))

    def test_compose_cannot_target_normal_project(self):
        with patch.object(host,'execute') as execute:
            for name in ('cu-engine-lab','cu-storage-'+'a'*32+'-1',PROJECT+'\n'):
                with self.assertRaises(ValueError): host.compose(name,'down','--volumes')
            execute.assert_not_called()

    def test_existing_project_refused(self):
        with patch.object(host,'execute',return_value='existing'),self.assertRaises(RuntimeError):host.ensure_new(PROJECT)

    def test_unlabelled_existing_volume_refused(self):
        with patch.object(host,'execute',side_effect=['','','',PROJECT+'_recovery_data']),self.assertRaises(RuntimeError):host.ensure_new(PROJECT)

    def test_wrong_container_or_mount_blocks_crash(self):
        for change in ('labels','volume','bind'):
            info=owned_info()
            if change=='labels': info['labels']['com.docker.compose.project']='cu-engine-lab'
            elif change=='volume': info['mounts'][0]['Name']='cu-engine-lab_db_data'
            else: info['mounts'][0]['Type']='bind'
            with patch.object(host,'inspect',return_value=info),patch.object(host,'execute') as execute:
                with self.assertRaises(RuntimeError):host.apply_stop(PROJECT,'id','sigkill')
                execute.assert_not_called()

    def test_sigkill_requires_137_and_not_oom(self):
        for exit_code,oom in ((0,False),(137,True)):
            stopped=owned_info(False,exit_code);stopped['state']['OOMKilled']=oom
            with patch.object(host,'inspect',side_effect=[owned_info(),stopped]),patch.object(host,'execute'):
                with self.assertRaises(RuntimeError):host.apply_stop(PROJECT,'id','sigkill')
        with patch.object(host,'inspect',side_effect=[owned_info(),owned_info(False,137)]),patch.object(host,'execute') as execute:
            self.assertEqual(host.apply_stop(PROJECT,'id','sigkill')['ExitCode'],137)
            execute.assert_called_once_with(['docker','kill','--signal','KILL','id'])

    def test_clean_control_rejects_forced_shutdown(self):
        with patch.object(host,'inspect',side_effect=[owned_info(),owned_info(False,137)]),patch.object(host,'compose'):
            with self.assertRaises(RuntimeError):host.apply_stop(PROJECT,'id','clean')

    def test_receipt_needs_complete_ordered_acknowledgments(self):
        receipt=dict(engine='Aria',rows=100,seed=1,acknowledged_count=100,acknowledged_ids=list(range(1,101)),
                     in_flight_at_receipt=0,expected_dataset_sha256=host.dataset_digest(recovery.make_rows(100,1)))
        host.validate_receipt(receipt,'Aria',100,1)
        for key,value in [('in_flight_at_receipt',1),('acknowledged_count',99),('acknowledged_ids',list(range(100))),('expected_dataset_sha256','bad')]:
            with self.subTest(key=key), self.assertRaises(RuntimeError):host.validate_receipt({**receipt,key:value},'Aria',100,1)

    def test_prepare_holds_connection_after_receipt_without_postload_queries(self):
        connection=MagicMock();cursor=connection.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect=[(1,),('11.8.9-MariaDB',),('InnoDB',),('benchmark_events','DDL')]
        cursor.fetchall.side_effect=[[],[('innodb_flush_log_at_trx_commit','1')],[('autocommit','ON')]]
        cursor.rowcount=1
        def receipt_written(path,data):
            self.assertEqual(data['acknowledged_count'],100)
            self.assertEqual(cursor.execute.call_args.args[0],recovery.INSERT)
            connection.__exit__.assert_not_called()
        with patch.object(recovery,'guard'),patch.object(recovery,'connect',return_value=connection), \
             patch.object(recovery,'runtime_metadata',return_value={}),patch.object(recovery,'source_fingerprint',return_value={}), \
             patch.object(recovery,'save_receipt',side_effect=receipt_written) as receipt, \
             patch.object(recovery.time,'sleep',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):recovery.prepare('InnoDB',100,1,Path('unused'))
        receipt.assert_called_once()
        self.assertFalse(any(c.args[0].startswith(('SELECT event_id','ANALYZE','FLUSH','CHECK')) for c in cursor.execute.call_args_list))

    def test_unreadable_table_does_not_become_zero_survival(self):
        class DBError(Exception): pass
        driver=SimpleNamespace(MySQLError=DBError)
        conn=MagicMock();cursor=conn.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect=[None,DBError(145,'crashed'),None]
        cursor.fetchall.return_value=[('engine_lab.benchmark_events','check','error','marked crashed')]
        with patch.dict('sys.modules',{'pymysql':driver}),patch.object(recovery,'guard'),patch.object(recovery,'connect',return_value=conn):
            result=recovery.observe(100,1,1)
        self.assertEqual(result['status'],'unreadable');self.assertEqual(result['error_code'],145)
        self.assertNotIn('missing_ids',result)
        self.assertEqual(cursor.execute.call_count,3)

    def test_authentication_failure_is_not_retried_or_called_data_loss(self):
        class DBError(Exception): pass
        with patch.dict('sys.modules',{'pymysql':SimpleNamespace(MySQLError=DBError)}),patch.object(recovery,'guard'),patch.object(recovery,'connect',side_effect=DBError(1045,'denied')) as connect:
            result=recovery.observe(100,1,1)
        self.assertEqual(result['status'],'unavailable');connect.assert_called_once()

    def test_partial_reports_rejected(self):
        with self.assertRaises(ValueError):host.markdown({'status':'failed'})
        with self.assertRaises(ValueError):host.markdown(dict(status='completed',rounds=1,trials=[]))

    def test_startup_failure_retains_evidence_and_never_kills_or_deletes(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for path in ('.env','compose.recovery.yaml','Dockerfile','scripts/run_recovery.py','benchmarks/recovery.py'):
                p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
            def fail_start(project,*args,**kw):
                if args[0]=='up':raise RuntimeError('simulated start failure')
            with patch.object(host,'ROOT',root),patch.object(host,'execute',return_value='linux') as execute,patch.object(host,'ensure_new'),patch.object(host,'compose',side_effect=fail_start) as compose:
                with self.assertRaisesRegex(RuntimeError,'simulated'):
                    host.run(SimpleNamespace(rows=100,seed=1,pilot=True,power_condition='test'))
            path=next((root/'results').glob('*/results.json'));result=json.loads(path.read_text())
            self.assertEqual(result['status'],'failed');self.assertIn('active_project',result)
            self.assertFalse(path.with_name('summary.md').exists())
            self.assertFalse(any(c.args[1]=='down' for c in compose.call_args_list))
            self.assertFalse(any('kill' in c.args[0] for c in execute.call_args_list))

    def test_check_table_errors_retain_even_matching_data(self):
        rows=recovery.make_rows(100,1);observation=recovery.compare_rows(rows,rows)
        observation['check_table_messages']=[('table','check','error','index damaged')]
        self.assertFalse(host.ordinary_outcome('MyISAM',observation))

    def test_complete_pilot_records_both_conditions_and_retains_unreadable_trials(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for name in ('.env','compose.recovery.yaml','Dockerfile','scripts/run_recovery.py','benchmarks/recovery.py'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('fixture')
            active={};events=[]
            def fake_compose(project,*args,**kwargs):
                events.append(args[0])
                if args[0]=='run' and '-d' in args:
                    active['engine']=args[args.index('--engine')+1]
                    return 'a'*64
                if args[0]=='run' and 'observe' in args:
                    self.assertIn('stop_applied',events)
                    rows=recovery.make_rows(100,1)
                    if active['engine']=='MyISAM':return json.dumps(dict(status='unreadable',error_code=145))
                    return json.dumps(recovery.compare_rows(rows,[] if active['engine']=='MEMORY' else rows))
                return ''
            def receipt(project,writer,path):
                data=dict(engine=active['engine'],rows=100,seed=1,acknowledged_count=100,
                    acknowledged_ids=list(range(1,101)),in_flight_at_receipt=0,
                    expected_dataset_sha256=host.dataset_digest(recovery.make_rows(100,1)))
                path.write_text(json.dumps(data));events.append('acknowledged');return data
            def stop(project,db,mode):
                self.assertIn('acknowledged',events);events.append('stop_applied')
                return dict(Status='exited',ExitCode=0 if mode=='clean' else 137,OOMKilled=False)
            def execute(args,**kwargs):
                if args[1]=='info':return 'linux'
                if args[1]=='exec':return 'mariadbd'
                if args[1]=='logs':return 'restart evidence'
                return ''
            with patch.object(host,'ROOT',root),patch.object(host,'execute',side_effect=execute),patch.object(host,'ensure_new'), \
                 patch.object(host,'compose',side_effect=fake_compose) as compose,patch.object(host,'get_db',return_value=('b'*64,owned_info())), \
                 patch.object(host,'inspect',return_value=owned_info()),patch.object(host,'validate_db'), \
                 patch.object(host,'validate_writer',return_value={'image_id':'writer-image'}), \
                 patch.object(host,'wait_receipt',side_effect=receipt),patch.object(host,'apply_stop',side_effect=stop):
                host.run(SimpleNamespace(rows=100,seed=1,pilot=True,power_condition='test'))
            path=next((root/'results').glob('*/results.json'));result=json.loads(path.read_text())
            self.assertEqual(result['status'],'completed');self.assertEqual(len(result['trials']),10)
            self.assertEqual(len(result['retained_projects']),2)
            self.assertEqual(sum(c.args[1]=='down' for c in compose.call_args_list),8)
            self.assertEqual(len(list(path.parent.glob('*/restart.log'))),10)
            self.assertEqual(path.with_name('summary.md').read_text(),host.markdown(result))
            self.assertNotIn('active_project',result)

if __name__=='__main__':unittest.main()
