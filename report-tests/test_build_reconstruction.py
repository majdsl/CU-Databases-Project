"""The optional snapshot experiment must refuse local/capacity-unsafe builds."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import check_build_reconstruction as reconstruction


class BuildReconstructionTests(unittest.TestCase):
    def test_local_invocation_refuses_before_build_or_credentials_mutation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(reconstruction.os.environ, {}, clear=True), \
                patch.object(reconstruction, 'output', return_value='a' * 40) as output, \
                patch.object(reconstruction, 'logged') as logged:
            with self.assertRaisesRegex(RuntimeError, 'disposable GitHub-hosted'):
                reconstruction.run(Path(tmp))
            self.assertEqual(output.call_args_list[0].args, ('git', 'rev-parse', 'HEAD'))
            self.assertEqual(output.call_count, 1)
            logged.assert_not_called()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_copying_storage_driver_refuses_before_build_and_records_capacity(self):
        environment = dict(GITHUB_ACTIONS='true', RUNNER_ENVIRONMENT='github-hosted',
            GITHUB_SHA='a' * 40, GITHUB_SERVER_URL='https://github.com',
            GITHUB_REPOSITORY='example/repo', GITHUB_RUN_ID='123')
        docker = dict(driver='vfs', root='/var/lib/docker', memory_bytes=8 * 1024**3, cpus=4)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(reconstruction.os.environ, environment, clear=True), \
                patch.object(reconstruction, 'output', side_effect=['a' * 40, '', json.dumps(docker)]), \
                patch.object(reconstruction.shutil, 'disk_usage', return_value=(50 * 1024**3, 1024, 49 * 1024**3)), \
                patch.object(reconstruction, 'logged') as logged:
            with self.assertRaisesRegex(RuntimeError, 'non-vfs'):
                reconstruction.run(Path(tmp))
            self.assertEqual(logged.call_count, 1)
            self.assertEqual(logged.call_args.args[1], 'preflight-resources')
            record = json.loads((Path(tmp) / 'preflight.json').read_text())
            self.assertEqual(record['docker']['driver'], 'vfs')

    def test_image_record_omits_secrets_and_retains_selected_runtime_configuration(self):
        image = 'sha256:' + 'a' * 64
        info = dict(Id=image, Os='linux', Architecture='amd64', Created='2026-11-01T00:00:00Z',
            RootFS=dict(Type='layers', Layers=['sha256:' + 'b' * 64]),
            Config=dict(Env=['PASSWORD=PRIVATE-MARKER'], Labels={'private': 'PRIVATE-MARKER'},
                Volumes={'/var/lib/mysql': {}}, Entrypoint=['docker-entrypoint.sh'], Cmd=['mariadbd']),
            History=['PRIVATE-MARKER'], GraphDriver={'private': 'PRIVATE-MARKER'})
        with patch.object(reconstruction, 'output', return_value=json.dumps([info])):
            record = reconstruction.image_record(image)
        self.assertNotIn('PRIVATE-MARKER', json.dumps(record))
        self.assertEqual(record['runtime_configuration']['Cmd'], ['mariadbd'])
        self.assertEqual(record['image_id'], image)
