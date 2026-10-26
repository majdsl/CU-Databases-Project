"""Prevent the restart-capable tutorial CI driver from targeting a normal lab."""
import unittest
from unittest.mock import patch
from scripts import check_tutorial


class TutorialDriverTests(unittest.TestCase):
    def test_normal_or_malformed_projects_rejected_before_docker(self):
        for name in ('cu-engine-lab', 'main', '', 'cu-ci-demo-1', 'cu-ci-123-1\n'):
            with self.subTest(project=name), patch.object(check_tutorial, 'command') as command:
                with self.assertRaises(ValueError):
                    check_tutorial.run(name)
                command.assert_not_called()


if __name__ == '__main__':
    unittest.main()
