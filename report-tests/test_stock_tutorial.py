"""Protect existing Docker resources and private credentials in the stock runner."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from scripts import check_stock_tutorial as stock


class StockTutorialTests(unittest.TestCase):
    def test_normal_projects_rejected_before_files_or_docker(self):
        for project in ('cu-engine-lab', '', 'main', 'cu-ci-123-1',
                        'cu-stock-demo', 'cu-stock-123-1-amd64\n'):
            with self.subTest(project=project), patch.object(stock.subprocess, 'run') as run:
                with self.assertRaises(ValueError):
                    stock.StockTutorial(project=project)
                run.assert_not_called()

    def test_existing_container_or_volume_is_not_reused(self):
        info = json.dumps(dict(os='linux', architecture='amd64'))
        for replies in ((info, 'existing-id'), (info, '', 'cu-stock-123-1-amd64-data')):
            with self.subTest(replies=replies):
                lab = stock.StockTutorial(project='cu-stock-123-1-amd64')
                lab.command = Mock(side_effect=replies)
                with self.assertRaisesRegex(RuntimeError, 'already exists'):
                    lab.start()
                actions = [call.args[0][:2] for call in lab.command.call_args_list]
                self.assertNotIn(['volume', 'create'], actions)
                self.assertNotIn(['container', 'create'], actions)
                self.assertFalse(lab.volume_created)
                self.assertIsNone(lab.container_id)

    def test_foreign_container_or_volume_is_never_removed(self):
        for kind in ('container', 'volume'):
            with self.subTest(kind=kind):
                lab = stock.StockTutorial(project='cu-stock-123-1-amd64')
                lab.volume_created = True
                labels = {stock.PROJECT_LABEL: lab.project, stock.OWNER_LABEL: 'another-owner'}
                if kind == 'container':
                    lab.container_id = 'c' * 64
                    lab.image_id = 'sha256:expected'
                    info = dict(Id=lab.container_id, Image=lab.image_id,
                                Config=dict(Image=stock.IMAGE, Labels=labels),
                                Mounts=[dict(Destination='/var/lib/mysql', Name=lab.volume, Type='volume')])
                else:
                    info = dict(Name=lab.volume, Labels=labels)
                lab.command = Mock(return_value=json.dumps([info]))
                with self.assertRaisesRegex(RuntimeError, 'ownership mismatch'):
                    lab.cleanup()
                self.assertEqual(lab.command.call_count, 1)
                self.assertEqual(lab.command.call_args.args[0][1], 'inspect')

    def test_logs_redact_passwords_and_omit_private_inspection(self):
        with tempfile.TemporaryDirectory() as directory:
            lab = stock.StockTutorial(output=directory)
            fake = subprocess.CompletedProcess([], 0, json.dumps({'Env': list(lab.passwords)}), '')
            with patch.object(stock.subprocess, 'run', return_value=fake), redirect_stdout(io.StringIO()):
                returned = lab.command(['container', 'inspect', 'owned'], private_output=True)
            self.assertIn(lab.passwords[0], returned)  # Available in memory for identity checks only.
            fake = subprocess.CompletedProcess([], 1, '', 'failure: ' + ' '.join(lab.passwords))
            with patch.object(stock.subprocess, 'run', return_value=fake), redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(RuntimeError, r'\[REDACTED\]'):
                    lab.command(['logs', 'owned'])
            saved = (Path(directory)/'transcript.txt').read_text() + json.dumps(lab.records)
            for password in lab.passwords:
                self.assertNotIn(password, saved)

    def test_expected_native_architecture_is_checked_before_creating_resources(self):
        lab = stock.StockTutorial(expected_arch='arm64')
        lab.command = Mock(return_value=json.dumps(dict(os='linux', architecture='amd64')))
        with self.assertRaisesRegex(RuntimeError, 'native Linux architecture match'):
            lab.start()
        self.assertEqual(lab.command.call_count, 1)


if __name__ == '__main__':
    unittest.main()
