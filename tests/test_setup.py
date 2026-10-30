"""Failure gates must prevent later build/database actions in the setup wrapper."""
from pathlib import Path
import io
import os
import shlex
import stat
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from scripts import setup_project


class SetupTests(unittest.TestCase):
    def successful_setup(self, directory, host_platform="linux", fail_probe=False):
        calls = []
        output = io.StringIO()

        def run(argv, **kwargs):
            calls.append(argv)
            if fail_probe and "-c" in argv:
                raise subprocess.CalledProcessError(1, argv)
            return subprocess.CompletedProcess(argv, 0, stdout="linux/x86_64\n")

        with patch.object(setup_project, "ROOT", Path(directory)), patch.object(
                setup_project.sys, "platform", host_platform), patch.object(
                setup_project.shutil, "which", return_value=None), patch.object(
                setup_project.subprocess, "run", side_effect=run), patch(
                "sys.stdout", output):
            if fail_probe:
                with self.assertRaises(RuntimeError) as error:
                    setup_project.setup("test-setup")
                return calls, output.getvalue(), str(error.exception)
            setup_project.setup("test-setup")
        return calls, output.getvalue(), None

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

    def test_linux_access_guidance_precedes_credentials_download_and_build(self):
        with tempfile.TemporaryDirectory() as directory:
            _, output, _ = self.successful_setup(directory)
        for label in ("Preserve or create local credentials", "Fetch and verify route data",
                      "Build Python runner"):
            self.assertLess(output.index("Native Linux output prerequisite"), output.index(label))
        self.assertIn("container write probe is authoritative", output)
        self.assertIn("SETUP PASS", output)

    def test_scoped_linux_repair_commands_quote_paths_with_spaces_and_apostrophes(self):
        root = Path("/tmp/owner's project")
        with patch.object(setup_project, "ROOT", root), patch.object(
                setup_project.sys, "platform", "linux"), patch.object(
                setup_project.shutil, "which", return_value="/usr/bin/setfacl"):
            output = setup_project.output_access_guidance()
        commands = [shlex.split(line.strip()) for line in output.splitlines()
                    if line.startswith("  ")]
        self.assertEqual(commands, [
            ["mkdir", "-p", "--", str(root / "results")],
            ["setfacl", "-m", "u:10001:rwx", "--", str(root / "results")],
        ])

    def test_missing_setfacl_has_install_hint_but_does_not_reject_existing_access(self):
        with tempfile.TemporaryDirectory() as directory:
            _, output, _ = self.successful_setup(directory)
        self.assertIn("setfacl is not on PATH", output)
        self.assertIn("sudo apt-get install acl", output)
        self.assertIn("existing ACLs may already grant access", output)
        self.assertIn("SETUP PASS", output)

    @unittest.skipUnless(os.name == "posix", "POSIX ownership/mode preservation")
    def test_existing_results_ownership_modes_and_contents_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory) / "results"
            results.mkdir(mode=0o750)
            evidence = results / "keep.txt"
            evidence.write_text("preserve this evidence\n", encoding="utf-8")
            before = results.stat()
            self.successful_setup(directory)
            after = results.stat()
            self.assertEqual((after.st_uid, after.st_gid, stat.S_IMODE(after.st_mode)),
                             (before.st_uid, before.st_gid, stat.S_IMODE(before.st_mode)))
            self.assertEqual(evidence.read_text(encoding="utf-8"), "preserve this evidence\n")

    def test_failed_probe_prints_exact_linux_repair_and_prevents_database_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            calls, _, error = self.successful_setup(directory, fail_probe=True)
            expected = "setfacl -m u:10001:rwx -- " + shlex.quote(str(Path(directory) / "results"))
        self.assertIn(expected, error)
        self.assertIn("Rootless/user-remapped Docker and SELinux", error)
        self.assertFalse(any("up" in call or call[-2:] == ["build", "db"] for call in calls))
        self.assertFalse(any("-m" in call and "unittest" in call for call in calls))

    def test_windows_never_recommends_posix_permission_commands(self):
        with tempfile.TemporaryDirectory() as directory:
            _, output, _ = self.successful_setup(directory, host_platform="win32")
            _, _, error = self.successful_setup(directory, host_platform="win32", fail_probe=True)
        self.assertNotIn("setfacl", output + error)
        self.assertNotIn("apt-get", output + error)
        self.assertIn("Docker Desktop file sharing", error)


if __name__ == "__main__":
    unittest.main()
