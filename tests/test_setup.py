"""Failure gates must prevent later build/database actions in the setup wrapper."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import setup_project


class SetupTests(unittest.TestCase):
    def exercise(self, fail_marker=None, platform="linux/x86_64\n"):
        calls = []

        def run(argv, **kwargs):
            calls.append(argv)
            if fail_marker and fail_marker(argv):
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 0, stdout=platform)

        with tempfile.TemporaryDirectory() as directory:
            with patch.object(setup_project, "ROOT", Path(directory)), patch.object(
                    setup_project.subprocess, "run", side_effect=run):
                with self.assertRaises(RuntimeError):
                    setup_project.setup("test-setup")
        return calls

    def test_wrong_platform_stops_before_credentials_or_build(self):
        calls = self.exercise(platform="windows/amd64\n")
        self.assertEqual(len(calls), 1)

    def test_invalid_dataset_stops_before_build_or_database(self):
        calls = self.exercise(lambda args: "scripts/fetch_openflights.py" in args)
        self.assertFalse(any("build" in c or "up" in c for c in calls))

    def test_unwritable_output_stops_before_database_start(self):
        calls = self.exercise(lambda args: "-c" in args)
        self.assertFalse(any("up" in c or c[-2:] == ["build", "db"] for c in calls))


if __name__ == "__main__":
    unittest.main()
