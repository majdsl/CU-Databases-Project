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
            with patch.object(host,'ROOT',root),patch.object(host,'execute',side_effect=lambda argv,capture=False:'linux/amd64' if argv[1]=='info' else 'vtest'),patch.object(host,'ensure_new'),patch.object(host,'compose',side_effect=compose),patch.object(host,'build_images',return_value=({'db':'sha256:'+'a'*64,'runner':'sha256:'+'b'*64},root/'runtime.json')):
                with self.assertRaises(RuntimeError):host.run('smoke','test')
            result=json.loads(next(root.glob('results/*/results.json')).read_text())
            self.assertEqual(result['status'],'failed');self.assertIn('active_project',result)
            self.assertTrue(any(a[0]=='up' for a in calls))
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


class ImmutableImageBindingTests(unittest.TestCase):
    def hosts(self):
        from scripts import run_write_diagnostics
        return ((host,'cu-pressure',1),(run_write_diagnostics,'cu-writes',2))

    @staticmethod
    def controls(cpus):
        return dict(runtime=dict(python='test',platform='Linux-test',pymysql='1.1.2',
                    cgroup_cpu_max=f'{cpus*100000} 100000',cgroup_memory_max='536870912'),
                    source_sha256={'Dockerfile':'d'*64},server_version='11.8.9-MariaDB-test',
                    global_variables={'query_cache_type':'OFF'},session_variables={'autocommit':'ON'})

    def test_build_uses_unique_tags_then_freezes_resolved_ids(self):
        for module,prefix,_ in self.hosts():
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp);ids={'db':'sha256:'+'a'*64,'runner':'sha256:'+'b'*64};queries=[]
                def execute(argv,capture=False):
                    queries.append(argv)
                    if argv[1:3]==['image','ls']:return ''
                    role='db' if argv[-1].endswith('-db:local') else 'runner'
                    return json.dumps(dict(id=ids[role],os='linux',architecture='amd64'))
                with patch.object(module,'execute',side_effect=execute),patch.object(module,'compose') as compose:
                    frozen,runtime=module.build_images(prefix+'-'+'1'*32+'-1',directory,'1'*32)
                self.assertEqual(frozen,ids)
                self.assertEqual(json.loads(runtime.read_text())['services'],
                                 {role:{'image':value} for role,value in ids.items()})
                build=json.loads((directory/'build-images.compose.json').read_text())
                self.assertEqual(build['services']['runner']['image'],prefix+'-'+'1'*32+'-runner:local')
                self.assertEqual(compose.call_args.args[1:],('build','db','runner'))
                self.assertTrue(all('engine-lab' not in query[-1] for query in queries))

    def test_build_tag_collision_prevents_build(self):
        for module,prefix,_ in self.hosts():
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                with patch.object(module,'execute',return_value='existing-image'),patch.object(module,'compose') as compose:
                    with self.assertRaisesRegex(RuntimeError,'tag already exists'):
                        module.build_images(prefix+'-'+'1'*32+'-1',Path(tmp),'1'*32)
                    compose.assert_not_called()

    def test_retagging_cannot_change_created_or_started_worker(self):
        import copy
        import subprocess
        for module,prefix,cpus in self.hosts():
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                directory=Path(tmp);project=prefix+'-'+'1'*32+'-1'
                selected='sha256:'+'b'*64;other='sha256:'+'c'*64
                legacy=prefix+'-runner:local'
                registry={selected:selected,other:other,legacy:selected}
                # A concurrent build retargets the old tag after image selection.
                registry[legacy]=other
                runtime=directory/'runtime.json';runtime.write_text(json.dumps({'services':{'runner':{'image':selected}}}))
                state={};actions=[];controls=self.controls(cpus)
                def compose(project,*args,**kwargs):
                    actions.append(args)
                    if args[0]=='ps':return 'owned' if state else ''
                    self.assertEqual(args,('create','--no-build','--pull','never','--no-recreate','runner'))
                    reference=json.loads(Path(kwargs['overrides'][0]).read_text())['services']['runner']['image']
                    state.update(Id='owned',Image=registry[reference],
                        Config=dict(Image=reference,Labels={'com.docker.compose.project':project,'com.docker.compose.service':'runner'}),
                        State=dict(Status='created',ExitCode=0,OOMKilled=False))
                    return ''
                def execute(argv,capture=False):
                    if argv[1]=='inspect':return json.dumps([copy.deepcopy(state)])
                    self.assertEqual(argv,['docker','rm','owned']);actions.append(('removed',));return 'owned'
                def start(argv,**kwargs):
                    self.assertEqual(argv,['docker','start','--attach','owned'])
                    self.assertEqual(state['Image'],selected)
                    state['State']['Status']='exited'
                    return subprocess.CompletedProcess(argv,0,json.dumps({'execution_controls':dict(before=controls,after=controls)}))
                with patch.object(module,'compose',side_effect=compose),patch.object(module,'execute',side_effect=execute),\
                     patch.object(module.subprocess,'run',side_effect=start):
                    result=module.run_worker(project,directory,'probe',[],{'runner':selected},runtime,controls['source_sha256'])
                self.assertEqual(result['execution_controls']['before'],controls)
                self.assertEqual(registry[legacy],other)
                self.assertIn(('removed',),actions)
                self.assertTrue((directory/'probe.json').is_file())

    def test_mismatched_image_is_refused_before_start_and_removal(self):
        for module,prefix,_ in self.hosts():
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                project=prefix+'-'+'1'*32+'-1';selected='sha256:'+'b'*64
                details=dict(Id='owned',Image='sha256:'+'c'*64,
                    Config=dict(Image=selected,Labels={'com.docker.compose.project':project,'com.docker.compose.service':'runner'}))
                replies=iter(('', '', 'owned'))  # initial collision check, create, identity ps
                with patch.object(module,'compose',side_effect=lambda *a,**k:next(replies)),\
                     patch.object(module,'execute',return_value=json.dumps([details])) as execute,\
                     patch.object(module.subprocess,'run') as start:
                    with self.assertRaisesRegex(RuntimeError,'frozen selection'):
                        module.run_worker(project,Path(tmp),'probe',[],{'runner':selected},Path(tmp)/'runtime.json',{})
                start.assert_not_called()
                self.assertFalse(any(call.args[0][1]=='rm' for call in execute.call_args_list))

    def test_abnormal_worker_exit_retains_stdout_and_container(self):
        import subprocess
        for module,prefix,_ in self.hosts():
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                created=dict(Id='owned',State=dict(Status='created',ExitCode=0,OOMKilled=False))
                failed=dict(Id='owned',State=dict(Status='exited',ExitCode=137,OOMKilled=True))
                raw='{"interrupted":true}\n'
                with patch.object(module,'compose',return_value=''),\
                     patch.object(module,'identity',side_effect=[created,failed]),\
                     patch.object(module.subprocess,'run',return_value=subprocess.CompletedProcess([],0,raw)),\
                     patch.object(module,'execute') as execute:
                    with self.assertRaisesRegex(RuntimeError,'retaining container'):
                        module.run_worker(prefix+'-'+'1'*32+'-1',Path(tmp),'probe',[],
                                          {'runner':'sha256:'+'b'*64},Path(tmp)/'runtime.json',{})
                self.assertEqual((Path(tmp)/'probe.json').read_text(),raw)
                execute.assert_not_called()

    def test_preexisting_worker_is_not_recreated(self):
        for module,prefix,_ in self.hosts():
            with self.subTest(module=module.__name__),tempfile.TemporaryDirectory() as tmp:
                with patch.object(module,'compose',return_value='existing') as compose,patch.object(module.subprocess,'run') as run:
                    with self.assertRaisesRegex(RuntimeError,'Existing worker'):
                        module.run_worker(prefix+'-'+'1'*32+'-1',Path(tmp),'probe',[],{},Path(tmp)/'runtime.json',{})
                self.assertEqual(compose.call_count,1);run.assert_not_called()

    def test_control_changes_and_wrong_resource_limits_are_rejected(self):
        import copy
        for module,_,cpus in self.hosts():
            reference=self.controls(cpus);source=reference['source_sha256']
            self.assertEqual(module.validate_controls(dict(before=reference,after=reference),source),reference)
            for field,value in (('global_variables',{'query_cache_type':'ON'}),('session_variables',{'autocommit':'OFF'}),
                                ('runtime',dict(reference['runtime'],python='different')),
                                ('source_sha256',{'Dockerfile':'0'*64}),('server_version','11.8.8-MariaDB-test')):
                changed=copy.deepcopy(reference);changed[field]=value
                for observed in (dict(before=reference,after=changed),dict(before=changed,after=changed)):
                    with self.subTest(module=module.__name__,field=field),self.assertRaises(RuntimeError):
                        module.validate_controls(observed,source,reference)
            for key,value in (('cgroup_cpu_max','300000 100000'),('cgroup_memory_max','1073741824')):
                changed=copy.deepcopy(reference);changed['runtime'][key]=value
                with self.subTest(module=module.__name__,resource=key),self.assertRaises(RuntimeError):
                    module.validate_controls(dict(before=changed,after=changed),source)

    def test_windows_host_source_paths_match_linux_copy(self):
        for module,_,_ in self.hosts():
            with self.subTest(module=module.__name__),patch('benchmarks.run.source_fingerprint',return_value={r'benchmarks\core.py':'d'*64}):
                self.assertEqual(module.worker_source(),{'benchmarks/core.py':'d'*64})


if __name__=='__main__':unittest.main()
