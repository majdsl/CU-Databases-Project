"""Build records: secret exclusion, immutable probes and honest registry identities."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import build_manifest as record


SECRET = 'PRIVATE-CREDENTIAL-MARKER'
DB = 'sha256:'+'b'*64
RUNNER = 'sha256:'+'c'*64
BASE = 'python:3.12-slim@sha256:'+'d'*64
CHILD = 'sha256:'+'e'*64
CONFIG = 'sha256:'+'f'*64
LAYER = 'sha256:'+'a'*64


class BuildManifestTests(unittest.TestCase):
    def image(self, image=DB):
        return dict(Id=image, Os='linux', Architecture='amd64', Created='2026-10-31T01:02:03.123Z',
                    RootFS=dict(Type='layers', Layers=[LAYER]),
                    Config=dict(Env=['PASSWORD='+SECRET], Labels={'private': SECRET},
                                Volumes={'/var/lib/mysql': {}}), History=[SECRET])

    def image_manifest(self):
        return dict(schemaVersion=2, mediaType='application/vnd.oci.image.manifest.v1+json',
                    config=dict(digest=CONFIG), layers=[dict(digest=LAYER)], annotations={'private': SECRET})

    def index(self):
        return dict(schemaVersion=2, mediaType='application/vnd.oci.image.index.v1+json',
                    manifests=[dict(digest=CHILD, platform=dict(os='linux', architecture='amd64')),
                               dict(digest=DB, platform=dict(os='linux', architecture='arm64'))],
                    annotations={'private': SECRET})

    def session(self):
        return dict(images={'db': DB, 'runner': RUNNER}, compose_version='2.39.4',
                    host=dict(commit='1'*40, build_manifest_helper_sha256=record.helper_sha256()),
                    source_sha256={'Dockerfile':'2'*64}, build_adapter_sha256='3'*64)

    def test_complete_collection_keeps_only_safe_fields_and_uses_selected_images(self):
        with tempfile.TemporaryDirectory(prefix='private path ') as tmp:
            root = Path(tmp)
            (root/'Dockerfile').write_text('FROM '+BASE+'\n# '+SECRET+'\n')
            config = dict(services={role: dict(build=dict(context=str(root), args={'PASSWORD':SECRET}),
                                              environment={'PASSWORD':SECRET}) for role in ('db', 'runner')},
                          secrets={'private':{'file':SECRET}})
            calls = []
            def command(argv, root, timeout=30):
                calls.append(argv)
                if argv == ['docker', 'compose', 'config']:
                    return json.dumps(config)
                if argv[:2] == ['docker', 'version']:
                    return json.dumps(dict(Client=dict(Version='28.4.0', Context=SECRET),
                                           Server=dict(Version='28.4.0', Name=SECRET)))
                if argv[:3] == ['docker', 'buildx', 'version']:
                    return 'github.com/docker/buildx v0.29.0 '+SECRET
                if argv[:3] == ['docker', 'buildx', 'inspect']:
                    return ('Name: '+SECRET+'\nDriver: docker\nNodes:\nName: '+SECRET+'\nEndpoint: '+SECRET+
                            '\nStatus: running\nBuildKit version: v0.25.0\nLabels:\n  private: '+SECRET+'\n')
                if argv[:4] == ['docker', 'buildx', 'imagetools', 'inspect']:
                    return json.dumps(self.index() if argv[-1] == BASE else self.image_manifest())
                if argv[:3] == ['docker', 'image', 'inspect']:
                    return json.dumps([self.image(argv[-1])])
                if argv[:2] == ['docker', 'run']:
                    if '/usr/bin/dpkg-query' in argv:
                        return 'libc6:amd64\t2.41-12+deb13u1\tamd64\tinstalled\n'
                    return json.dumps(dict(python_version='3.12.15', distributions=[dict(name='PyMySQL',version='1.1.1')]))
                self.fail('Unexpected build record command')
            with patch.object(record, 'command', side_effect=command):
                inputs=record.capture_inputs(root,['docker','compose','config'])
                result = record.collect(root, self.session(), ['docker', 'compose', 'config'], inputs)
            serialized = json.dumps(result)
            self.assertNotIn(SECRET, serialized)
            self.assertNotIn(str(root), serialized)
            self.assertEqual(result['build_adapter_sha256'], '3'*64)
            self.assertEqual(result['inputs']['db']['dockerfile_sha256'], hashlib.sha256((root/'Dockerfile').read_bytes()).hexdigest())
            self.assertEqual(result['images']['db']['image_id'], DB)
            self.assertEqual(result['tools']['builder'],dict(status='observed_without_bootstrap',driver='docker',
                                                            nodes=[dict(status='running',buildkit='v0.25.0')]))
            self.assertEqual(result['images']['runner']['python']['distributions'],[dict(name='PyMySQL',version='1.1.1')])
            self.assertEqual(result['inputs']['runner']['declared_bases'][0]['registry']['manifest_digest'], CHILD)
            self.assertEqual(len([c for c in calls if 'imagetools' in c]), 2)  # Same base resolved once.
            probes = [c for c in calls if c[:2] == ['docker', 'run']]
            self.assertEqual(len(probes), 3)
            for probe in probes:
                for flag in ('--rm','--pull=never','--network=none','--read-only','--cap-drop=ALL',
                             '--security-opt=no-new-privileges','--user=65534:65534'):
                    self.assertIn(flag, probe)
                self.assertIn('type=tmpfs,destination=/var/lib/mysql,tmpfs-size=1048576', probe)
                self.assertIn(probe[probe.index('--entrypoint')+2], (DB,RUNNER))
                self.assertNotIn('--env-file', probe)
                self.assertNotIn('--volume', probe)

    def test_effective_external_and_inline_dockerfiles_are_hashed_without_path_or_contents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'checkout'; root.mkdir()
            external=Path(tmp)/'private.Dockerfile'; external.write_text('FROM '+BASE+'\n# '+SECRET)
            config=dict(services=dict(db=dict(build=dict(context=str(root), dockerfile=str(external))),
                                      runner=dict(build=dict(context=str(root), dockerfile_inline='FROM '+BASE+'\n# '+SECRET))))
            result=record.effective_inputs(root,config)
            self.assertEqual(result['db']['dockerfile'], 'external Dockerfile (path omitted)')
            self.assertEqual(result['runner']['dockerfile'],'inline')
            self.assertNotIn(SECRET,json.dumps(result))
            self.assertNotIn(str(external),json.dumps(result))

    def test_effective_dockerfile_change_during_build_is_rejected_before_inventory(self):
        with patch.object(record,'capture_inputs',return_value={'changed':True}),patch.object(record,'tool_versions') as tools:
            with self.assertRaisesRegex(record.RecordError,'Dockerfiles changed'):
                record.collect(Path('/unused'),self.session(),[],{'original':True})
        tools.assert_not_called()

    def test_unresolved_or_unpinned_from_does_not_become_a_verified_base(self):
        config=dict(services={role:dict(build=dict(dockerfile_inline='ARG BASE\nFROM ${BASE}\n')) for role in ('db','runner')})
        result=record.effective_inputs(Path('/unused'),config)
        self.assertEqual(result['db']['declared_bases'],[dict(status='unavailable',reason='base_not_literal_digest_pin')])
        self.assertNotIn('${BASE}',json.dumps(result))

    def test_image_mismatch_platform_and_missing_layers_are_rejected(self):
        for key,value in [('Id',RUNNER),('Architecture','arm64'),('RootFS',{})]:
            image=self.image();image[key]=value
            with self.subTest(key=key),self.assertRaises(record.RecordError):
                record.image_metadata(image,DB)
        info,volumes=record.image_metadata(self.image(),DB)
        self.assertEqual(info['rootfs_diff_ids'],[LAYER])
        self.assertEqual(volumes,['/var/lib/mysql'])
        self.assertNotIn(SECRET,json.dumps(info))

    def test_inventory_rejects_malformed_duplicate_and_empty_installed_records(self):
        bad=['','package\t1.0\tamd64\n','package\t1.0\tamd64\tunknown\n',
             'package\tPASSWORD='+SECRET+'\tamd64\tinstalled\n',
             'package\t1.0\tamd64\tinstalled\n'*2]
        for text in bad:
            with self.subTest(text=text),self.assertRaises(record.RecordError):
                record.package_inventory(text)
        self.assertEqual(record.package_inventory('removed\t\t\tconfig-files\npkg\t1:2.0+deb13u1\tall\tinstalled\n'),
                         [dict(name='pkg',version='1:2.0+deb13u1',architecture='all')])

    def test_python_inventory_normalized_duplicates_and_invalid_values_are_rejected(self):
        values=[dict(python_version='3.12.15',distributions=[]),
                dict(python_version=SECRET,distributions=[dict(name='pip',version='25.0')]),
                dict(python_version='3.12.15',distributions=[dict(name='A_B',version='1.0'),dict(name='a-b',version='1.0')])]
        for value in values:
            with self.subTest(value=value),self.assertRaises(record.RecordError):
                record.python_inventory(json.dumps(value))

    def test_registry_index_selects_correct_platform_and_never_copies_annotations(self):
        with patch.object(record,'command',side_effect=[json.dumps(self.index()),json.dumps(self.image_manifest())]) as command:
            result=record.registry_manifest(BASE,Path('/unused'))
        self.assertEqual(result['status'],'resolved')
        self.assertEqual(result['platform_selection'],'linux/amd64 index descriptor')
        self.assertEqual(result['manifest_digest'],CHILD)
        self.assertEqual(result['config_digest'],CONFIG)
        self.assertEqual(result['compressed_layer_digests'],[LAYER])
        self.assertNotIn(SECRET,json.dumps(result))
        for call in command.call_args_list:
            self.assertEqual(call.kwargs['timeout'],15)

    def test_builder_probe_has_no_bootstrap_and_retains_no_names_endpoints_or_environment(self):
        value=('Name: '+SECRET+'\nDriver: docker-container\nNodes:\nName: '+SECRET+'\nEndpoint: '+SECRET+
               '\nStatus: inactive\nBuildKit version: N/A\nDriver Options: private="'+SECRET+'"\nLabels:\n'+
               '  Status: '+SECRET+'\n  BuildKit version: '+SECRET+'\n')
        with patch.object(record,'command',return_value=value) as command:
            result=record.builder_details(Path('/unused'))
        self.assertEqual(result['nodes'],[dict(status='inactive',buildkit='unavailable')])
        self.assertNotIn(SECRET,json.dumps(result))
        self.assertNotIn('--bootstrap',command.call_args.args[0])
        self.assertEqual(command.call_args.args[0],['docker','buildx','inspect'])
        self.assertEqual(command.call_args.kwargs['timeout'],10)
        with patch.object(record,'command',side_effect=record.RecordError(SECRET)):
            result=record.builder_details(Path('/unused'))
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn(SECRET,json.dumps(result))

    def test_plain_builder_node_fields_remain_grouped_and_node_names_remain_private(self):
        value=('Name: '+SECRET+'\nDriver: docker-container\nNodes:\nName: private-1\nEndpoint: '+SECRET+
               '\nStatus: running\nBuildKit version: v0.24.0\nLabels:\n  private: '+SECRET+
               '\nName: private-2\nEndpoint: '+SECRET+'\nStatus: stopped\nBuildKit version: v0.23.2\n')
        with patch.object(record,'command',return_value=value):
            result=record.builder_details(Path('/unused'))
        self.assertEqual(result['nodes'],[dict(status='running',buildkit='v0.24.0'),
                                          dict(status='stopped',buildkit='v0.23.2')])
        self.assertNotIn('private-',json.dumps(result))
        self.assertNotIn(SECRET,json.dumps(result))

    def test_ambiguous_or_malformed_plain_builder_inspection_stays_unavailable(self):
        prefix='Name: private\nDriver: docker\nNodes:\nName: private-0\n'
        values=[prefix+'Status: running\nStatus: stopped\nBuildKit version: v0.24.0\n',
                prefix+'Status: running\nBuildKit version: '+SECRET+'\n',
                prefix+'Status: running\n',
                prefix+'Status: inactive\nName: private-0\nStatus: stopped\n',
                prefix+'BuildKit version: v0.24.0\n',
                'Driver: docker\nStatus: running\nBuildKit version: v0.24.0\n',
                prefix+'Status: inactive\nDriver: remote\n',
                prefix+'Status: inactive\nNodes:\n',
                SECRET]
        for value in values:
            with self.subTest(value=value),patch.object(record,'command',return_value=value):
                result=record.builder_details(Path('/unused'))
            self.assertEqual(result['status'],'unavailable')
            self.assertNotIn(SECRET,json.dumps(result))

    def test_registry_ambiguity_and_failures_are_explicitly_unavailable(self):
        index=self.index();index['manifests'].append(copy.deepcopy(index['manifests'][0]))
        for value in [index, dict(schemaVersion=1), {'schemaVersion':2,'mediaType':'unsupported'}]:
            with patch.object(record,'command',return_value=json.dumps(value)):
                self.assertEqual(record.registry_manifest(BASE,Path('/unused'))['status'],'unavailable')
        with patch.object(record,'command',side_effect=record.RecordError(SECRET)):
            result=record.registry_manifest(BASE,Path('/unused'))
        self.assertEqual(result['status'],'unavailable')
        self.assertNotIn(SECRET,json.dumps(result))

    def test_direct_registry_manifest_does_not_assert_platform_was_verified(self):
        with patch.object(record,'command',return_value=json.dumps(self.image_manifest())):
            result=record.registry_manifest(BASE,Path('/unused'))
        self.assertEqual(result['status'],'resolved')
        self.assertIn('platform not established',result['platform_selection'])

    def test_command_failures_and_timeout_do_not_expose_stderr_or_credentials(self):
        for outcome in [subprocess.CompletedProcess([],1,SECRET.encode()),
                        subprocess.TimeoutExpired(['password='+SECRET],15,output=SECRET.encode())]:
            kwargs={'side_effect':outcome} if isinstance(outcome,Exception) else {'return_value':outcome}
            with patch.object(record.subprocess,'run',**kwargs) as run:
                with self.assertRaises(record.RecordError) as caught:
                    record.command(['docker','compose','config'],Path('/unused'))
            self.assertNotIn(SECRET,str(caught.exception))
            self.assertIs(run.call_args.kwargs['stderr'],subprocess.DEVNULL)
            self.assertEqual(run.call_args.kwargs['timeout'],30)

    def test_build_record_hash_and_identity_binding_reject_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'session.json';manifest=path.parent/'build-manifest.json'
            session=self.session()
            value=dict(format_version=1,collector_sha256=session['host']['build_manifest_helper_sha256'],
                       source_commit=session['host']['commit'],source_sha256=session['source_sha256'],
                       build_adapter_sha256=session['build_adapter_sha256'],
                       images={role:dict(image_id=image) for role,image in session['images'].items()})
            manifest.write_text(json.dumps(value))
            session['build_manifest']=dict(file=manifest.name,sha256=hashlib.sha256(manifest.read_bytes()).hexdigest())
            record.verify(path,session)
            manifest.write_text(json.dumps(value)+'\n')
            with self.assertRaisesRegex(record.RecordError,'checksum'):
                record.verify(path,session)
            value['images']['db']['image_id']=RUNNER;manifest.write_text(json.dumps(value))
            session['build_manifest']['sha256']=hashlib.sha256(manifest.read_bytes()).hexdigest()
            with self.assertRaisesRegex(record.RecordError,'identities'):
                record.verify(path,session)
            session['build_manifest']['file']='../outside.json'
            with self.assertRaises(record.RecordError):record.verify(path,session)


if __name__ == '__main__':
    unittest.main()
