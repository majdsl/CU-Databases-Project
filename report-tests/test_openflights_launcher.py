"""Host launcher guards: immutable selection, staged drift and retained failures."""
import copy
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from scripts import run_openflights as host

SOURCE_ROOT = Path(__file__).resolve().parents[1]


class LauncherTests(unittest.TestCase):
    def setUp(self):
        # Host guards remain offline; endpoint behavior itself is exercised below.
        self.endpoint_implementation = host.local_docker_endpoint
        endpoint = patch.object(host, 'local_docker_endpoint', return_value='unix')
        endpoint.start()
        self.addCleanup(endpoint.stop)

    def fixture(self, root):
        directory = root/'results'/'session with spaces'; directory.mkdir(parents=True)
        path = directory/'session.json'
        session = dict(format_version=1, experiment='immutable_openflights_v1', token='a'*32,
            project='cu-openflights-'+'a'*32, images={'db':'sha256:'+'b'*64,'runner':'sha256:'+'c'*64},
            status='prepared', stages={}, commands=[], host={'commit':'tested'},
            source_sha256={'example.py':'d'*64}, dataset_sha256='e'*64, rows=67663, power_condition=None,
            docker_endpoint_kind='unix')
        host.save_json(path, session)
        host.save_json(directory/'runtime-images.compose.json', host.expected_runtime(session))
        return session, path

    def controls(self, session):
        return dict(source_sha256=session['source_sha256'],dataset_sha256=session['dataset_sha256'],
            rows=session['rows'],runtime={'cgroup_cpu_max':'100000 100000','cgroup_memory_max':'536870912'},
            server_version='11.8.9-MariaDB-test',global_variables={'query_cache_type':'OFF'},
            session_variables={'query_cache_type':'OFF','autocommit':'ON','max_heap_table_size':'134217728',
                               'sql_mode':'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'})

    def details(self, session, role='runner', status='created', exit_code=0):
        db = role == 'db'
        return dict(Id=role+'-owned',Image=session['images'][role],
            Config={'Image':session['images'][role], 'Labels':{
                'com.docker.compose.project':session['project'],'com.docker.compose.service':role,
                host.OWNER_LABEL:session['token']}},
            HostConfig={'NanoCpus':2000000000 if db else 1000000000,
                        'Memory':2147483648 if db else 536870912,'PortBindings':{}},
            Mounts=[{'Type':'volume' if db else 'bind','Name':session['project']+'_db_data' if db else None,
                     'Destination':'/var/lib/mysql' if db else '/results','RW':True}],
            State={'Status':status,'ExitCode':exit_code,'OOMKilled':False,'StartedAt':'original-start'})

    def test_normal_project_and_existing_unlabelled_volume_are_refused(self):
        with patch.object(host,'execute') as execute:
            with self.assertRaisesRegex(RuntimeError,'Invalid isolated'):
                host.ensure_new('cu-engine-lab')
            execute.assert_not_called()
        project='cu-openflights-'+'a'*32
        with patch.object(host,'execute',side_effect=['','','',project+'_db_data']):
            with self.assertRaisesRegex(RuntimeError,'volume name already exists'):
                host.ensure_new(project)

    def test_runtime_override_tampering_refused(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp))
            host.load_session(path)
            altered=host.expected_runtime(session);altered['services']['runner']['image']='mutable:tag'
            host.save_json(path.parent/'runtime-images.compose.json',altered)
            with self.assertRaisesRegex(RuntimeError,'runtime override changed'):
                host.load_session(path)

    def test_prepare_builds_unique_tags_then_binds_only_ids(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            root=Path(tmp);(root/'.env').write_text('fixture secret not consumed')
            (root/'results').mkdir()
            images={'db':'sha256:'+'b'*64,'runner':'sha256:'+'c'*64}
            def execute(argv,capture=False):
                if argv[1]=='info': return 'linux/amd64'
                if argv[1:3]==['compose','version']: return 'test-compose'
                if argv[1:3]==['image','ls']:return ''
                role='db' if argv[-1].endswith('-db:local') else 'runner'
                return json.dumps({'id':images[role],'os':'linux','architecture':'amd64'})
            with patch.object(host,'execute',side_effect=execute),patch.object(host,'ensure_new'),\
                 patch.object(host,'compose') as compose,patch.object(host,'host_identity',return_value={'commit':'tested'}),\
                 patch.object(host,'source_hashes',return_value={}),patch.object(host.benchmark,'load_dataset',return_value=({},[(1,)])):
                path=host.prepare()
            data=json.loads(path.read_text())
            self.assertEqual(data['images'],images)
            self.assertEqual(json.loads((path.parent/'runtime-images.compose.json').read_text()),host.expected_runtime(data))
            self.assertEqual(compose.call_args.args[2:],('build','db','runner'))
            self.assertEqual(data['status'],'prepared')
            self.assertNotIn('fixture secret',path.read_text())

    def test_paths_with_spaces_stay_single_arguments(self):
        with tempfile.TemporaryDirectory(prefix='launcher space ') as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp))
            with patch.object(host,'execute',return_value='') as execute:
                host.compose(session,path,'ps','-a','-q','runner',capture=True,
                             overrides=[path.parent/'runtime-images.compose.json'])
            argv=execute.call_args.args[0]
            self.assertIn(str(Path(tmp)/'.env'),argv)
            self.assertIn(str(path.parent/'runtime-images.compose.json'),argv)
            self.assertIn(session['project'],argv)
            self.assertNotIn('fixture secret',path.read_text())

    def test_source_change_refused_before_database(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp))
            with patch.object(host,'source_hashes',return_value={'different':'source'}),\
                 patch.object(host,'start_database') as start:
                with self.assertRaisesRegex(RuntimeError,'source/revision changed'):
                    host.run_stage(path,'pilot','same power')
                start.assert_not_called()
            self.assertEqual(json.loads(path.read_text())['status'],'prepared')

    def test_remote_docker_endpoint_refused_without_contacting_daemon(self):
        with patch.dict(os.environ, {'DOCKER_HOST': 'tcp://remote.example:2376'}, clear=True), \
                patch.object(host, 'execute') as execute:
            with self.assertRaisesRegex(RuntimeError, 'remote/TCP'):
                self.endpoint_implementation()
            execute.assert_not_called()
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(host, 'execute', side_effect=['remote', json.dumps('ssh://remote.example')]):
            with self.assertRaisesRegex(RuntimeError, 'remote/TCP'):
                self.endpoint_implementation()

    def test_explicit_context_takes_precedence_over_docker_host(self):
        with patch.dict(os.environ, {'DOCKER_CONTEXT': 'desktop-linux',
                                    'DOCKER_HOST': 'tcp://remote.example:2376'}, clear=True), \
                patch.object(host, 'execute', return_value=json.dumps('unix:///var/run/docker.sock')) as execute:
            self.assertEqual(self.endpoint_implementation(), 'unix')
            self.assertEqual(execute.call_args.args[0][0:4],
                             ['docker', 'context', 'inspect', 'desktop-linux'])

    def test_changed_endpoint_refused_before_database_operation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(host, 'ROOT', Path(tmp)):
            _, path = self.fixture(Path(tmp))
            with patch.object(host, 'local_docker_endpoint', return_value='npipe'), \
                    patch.object(host, 'start_database') as start:
                with self.assertRaisesRegex(RuntimeError, 'endpoint kind changed'):
                    host.run_stage(path, 'pilot', 'power')
                start.assert_not_called()

    def test_failed_or_already_attempted_stage_cannot_retry(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp))
            for status,stages in [('failed',{}),('prepared',{'pilot':{'status':'failed'}})]:
                session.update(status=status,stages=stages);host.save_json(path,session)
                with patch.object(host,'start_database') as start:
                    with self.assertRaises(RuntimeError):host.run_stage(path,'pilot','same power')
                    start.assert_not_called()

    def test_full_requires_unchanged_pilot_and_power(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp));session.update(status='pilot_completed',power_condition='original')
            session['stages']['pilot']={'status':'completed','result':{'run_id':'20261030T000000Z-openflights-12345678'}}
            raw=Path(tmp)/'results'/session['stages']['pilot']['result']['run_id'];raw.mkdir()
            for name,field in [('results.json','results_sha256'),('summary.md','summary_sha256')]:
                (raw/name).write_text('original');session['stages']['pilot']['result'][field]=hashlib.sha256(b'original').hexdigest()
            host.save_json(path,session)
            with patch.object(host,'source_hashes',return_value=session['source_sha256']),\
                 patch.object(host,'host_identity',return_value=session['host']),patch.object(host,'start_database') as start:
                with self.assertRaisesRegex(RuntimeError,'Power description changed'):
                    host.run_stage(path,'full','changed')
                start.assert_not_called()
                (raw/'results.json').write_text('tampered')
                with self.assertRaisesRegex(RuntimeError,'Pilot evidence changed'):
                    host.run_stage(path,'full','original')
                start.assert_not_called()

    def exercise_worker(self,root,wrong_image=False,exit_code=0,drift=False,db_restart=False):
        session,path=self.fixture(root);session['stages']['smoke']={'status':'running'}
        db=self.details(session,'db','running');session['database']=host.recorded_identity(db)
        current=self.controls(session);after_controls=copy.deepcopy(current)
        if drift:after_controls['global_variables']['query_cache_type']='ON'
        output=host.BEGIN+'\n'+json.dumps({'before':current,'after':after_controls})+'\n'+host.END+'\n'
        state={};calls=[]
        # Build tags are deliberately retargeted. Creation consumes the immutable override only.
        registry={session['images']['runner']:session['images']['runner'],session['project']+'-runner:local':'sha256:'+'f'*64}
        def compose(s,p,*args,**kwargs):
            calls.append(args)
            if args[0]=='ps':return 'worker-owned' if state else ''
            self.assertEqual(args,('create','--no-build','--pull','never','--no-recreate','runner'))
            selected=json.loads(Path(kwargs['overrides'][0]).read_text())['services']['runner']['image']
            state.update(self.details(session));state['Image']='sha256:'+'f'*64 if wrong_image else registry[selected]
            return ''
        def execute(argv,capture=False):
            calls.append(tuple(argv))
            if argv[:2]==['docker','inspect']:return json.dumps([state])
            if argv[:2]==['docker','rm']:state['removed']=True;return ''
            raise AssertionError(argv)
        actual_identity=host.identity
        def identity(s,p,role):
            if role=='db':
                result=copy.deepcopy(db)
                if db_restart:result['State']['StartedAt']='different-start'
                return result
            return actual_identity(s,p,role)
        def start(argv,**kwargs):
            state['State'].update(Status='exited',ExitCode=exit_code)
            return subprocess.CompletedProcess(argv,exit_code,stdout=output)
        with patch.object(host,'compose',side_effect=compose),patch.object(host,'execute',side_effect=execute),\
             patch.object(host,'identity',side_effect=identity),patch.object(host.subprocess,'run',side_effect=start) as launch:
            if wrong_image or exit_code or drift or db_restart:
                with self.assertRaises(RuntimeError):host.run_worker(session,path,'smoke','correctness')
            else:host.run_worker(session,path,'smoke','correctness')
            if wrong_image:launch.assert_not_called()
        return session,path,state,calls

    def test_retagging_cannot_change_created_image_and_only_success_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path,state,calls=self.exercise_worker(Path(tmp))
            self.assertEqual(state['Image'],session['images']['runner'])
            self.assertTrue(state['removed'])
            self.assertEqual(session['stages']['smoke']['runner_before']['image_id'],session['images']['runner'])
            self.assertEqual(session['stages']['smoke']['database_after']['container_id'],'db-owned')

    def test_wrong_actual_image_refused_before_start(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            _,_,state,calls=self.exercise_worker(Path(tmp),wrong_image=True)
            self.assertNotIn('removed',state)
            self.assertFalse(any(c[:2]==('docker','rm') for c in calls))

    def test_failed_worker_and_control_drift_retain_output_and_container(self):
        for failure in ({'exit_code':1},{'drift':True},{'db_restart':True}):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
                _,path,state,calls=self.exercise_worker(Path(tmp),**failure)
                self.assertTrue((path.parent/'smoke-transcript.txt').is_file())
                self.assertNotIn('removed',state)
                self.assertFalse(any(c[:2]==('docker','rm') for c in calls))

    def test_failure_checkpoint_preserves_session_and_refuses_retry(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp))
            with patch.object(host,'source_hashes',return_value=session['source_sha256']),\
                 patch.object(host,'host_identity',return_value=session['host']),patch.object(host,'start_database'),\
                 patch.object(host,'run_worker',side_effect=RuntimeError('worker failed')),patch.object(host,'stop') as stop:
                with self.assertRaises(RuntimeError):host.run_stage(path,'pilot','power')
                stop.assert_not_called()
            recorded=json.loads(path.read_text());self.assertEqual(recorded['status'],'failed')
            self.assertEqual(recorded['stages']['pilot']['status'],'failed')
            self.assertFalse((path.parent/'.operation.lock').exists())

    def test_wrong_database_owner_prevents_stop(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp));db=self.details(session,'db','running')
            db['Config']['Labels'][host.OWNER_LABEL]='someone-else'
            with patch.object(host,'compose',return_value='db-owned') as compose,\
                 patch.object(host,'execute',return_value=json.dumps([db])):
                with self.assertRaisesRegex(RuntimeError,'ownership mismatch'):host.stop(session,path)
            self.assertFalse(any(c.args[2]=='stop' for c in compose.call_args_list))

    def test_preexisting_worker_refused_without_creation(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(host,'ROOT',Path(tmp)):
            session,path=self.fixture(Path(tmp));session['stages']['smoke']={}
            with patch.object(host,'compose',return_value='already-there') as compose:
                with self.assertRaisesRegex(RuntimeError,'Pre-existing worker'):
                    host.run_worker(session,path,'smoke','correctness')
            self.assertEqual(compose.call_count,1)

    def worker_rejection(self, source_mismatch=False, version='11.8.9-MariaDB-test', settings=None):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'scripts').mkdir();(root/'data').mkdir()
            (root/'scripts/fetch_openflights.py').write_text('fixture')
            (root/'data/manifest.json').write_text('{}')
            b=types.ModuleType('benchmarks.openflights');b.ROOT=root;b.DATA=root/'data'
            b.load_dataset=MagicMock(return_value=({},[(1,)]));b.run=MagicMock()
            pkg=types.ModuleType('benchmarks');pkg.openflights=b
            core=types.ModuleType('benchmarks.core');core.dataset_digest=lambda rows:'digest'
            run=types.ModuleType('benchmarks.run');run.runtime_metadata=lambda:{'cgroup_cpu_max':'100000 100000','cgroup_memory_max':'536870912'}
            run.source_fingerprint=lambda:{'source':'actual'}
            values={'query_cache_type':'OFF','autocommit':'ON','max_heap_table_size':'134217728',
                    'sql_mode':'STRICT_ALL_TABLES,NO_ENGINE_SUBSTITUTION'}
            values.update(settings or {})
            run.variables=lambda cursor,scope:values
            mysql=types.ModuleType('pymysql');mysql.connect=MagicMock()
            mysql.connect.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value.fetchone.return_value=(version,)
            expected_source={'source':'different' if source_mismatch else 'actual'}
            for name in ['scripts/fetch_openflights.py','data/manifest.json']:
                expected_source[name if name.startswith('scripts') else 'data/manifest.json']=hashlib.sha256((root/name).read_bytes()).hexdigest()
            expected={'source_sha256':expected_source,'dataset_sha256':'digest','rows':1,'reference':None}
            modules={'benchmarks':pkg,'benchmarks.openflights':b,'benchmarks.core':core,'benchmarks.run':run,'pymysql':mysql}
            with patch.dict(sys.modules,modules),patch.object(sys,'argv',['worker','pilot','power',json.dumps(expected)]),\
                 patch.dict(os.environ,{'DB_HOST':'db','DB_USER':'fixture','DB_PASSWORD':'fixture'}),\
                 patch('tempfile.TemporaryDirectory'):
                with self.assertRaisesRegex(RuntimeError,'before workload'):exec(host.WORKER,{})
            b.run.assert_not_called()

    def test_before_workload_source_drift_rejected_inside_worker(self):
        self.worker_rejection(source_mismatch=True)

    def test_before_workload_incompatible_server_or_sql_never_starts_benchmark(self):
        self.worker_rejection(version='11.9.0-MariaDB-test')
        for settings in [{'query_cache_type':'ON'},{'autocommit':'OFF'},
                         {'max_heap_table_size':'1024'},{'sql_mode':'STRICT_ALL_TABLES'},
                         {'sql_mode':'NO_ENGINE_SUBSTITUTION'}]:
            with self.subTest(settings=settings):self.worker_rejection(settings=settings)

    def archived_result(self, root, mode):
        run = ('20261030T184911Z-openflights-329f0869' if mode == 'pilot'
               else '20261030T184936Z-openflights-85032cd6')
        source = SOURCE_ROOT/'evidence/openflights'/run
        target = root/'results'/run
        shutil.copytree(source, target)
        result = json.loads((target/'results.json').read_text())
        session = {key: result[key] for key in
                   ('dataset_sha256', 'rows', 'source_sha256', 'power_condition')}
        session['control_reference'] = {key: result[key] for key in
                                       ('runtime', 'server_version', 'global_variables', 'session_variables')}
        return session, target, 'Saved: /results/'+run+'\n'

    def test_completed_pilot_and_full_readback_preserves_original_bytes(self):
        for mode in ('pilot', 'full'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, \
                    patch.object(host, 'ROOT', Path(tmp)):
                session, target, output = self.archived_result(Path(tmp), mode)
                before = {p.name: p.read_bytes() for p in target.iterdir() if p.is_file()}
                record = host.read_result(output, mode, session)
                self.assertEqual(record['run_id'], target.name)
                self.assertEqual(record['results_sha256'], hashlib.sha256(before['results.json']).hexdigest())
                self.assertEqual(before, {p.name:p.read_bytes() for p in target.iterdir() if p.is_file()})

    def test_result_with_inconsistent_runtime_probe_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(host, 'ROOT', Path(tmp)):
            session, _, output = self.archived_result(Path(tmp), 'pilot')
            session['control_reference']['server_version'] = 'different-server'
            with self.assertRaisesRegex(RuntimeError, 'runtime probe: server_version'):
                host.read_result(output, 'pilot', session)

    def test_full_stage_cannot_accept_a_pilot_or_path_traversal_output(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(host, 'ROOT', Path(tmp)):
            session, _, output = self.archived_result(Path(tmp), 'pilot')
            with self.assertRaisesRegex(RuntimeError, 'run/configuration'):
                host.read_result(output, 'full', session)
            with self.assertRaisesRegex(RuntimeError, 'valid result directory'):
                host.read_result('Saved: /results/../../another-run\n', 'pilot', session)


if __name__=='__main__':
    unittest.main()
