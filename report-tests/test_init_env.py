"""Credential creation stays private and never replaces existing local values."""
import contextlib
import io
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import init_env


class InitEnvTests(unittest.TestCase):
    def run_generator(self, root, umask="022"):
        scripts = root / "scripts"
        scripts.mkdir(exist_ok=True)
        script = scripts / "init_env.py"
        shutil.copyfile(init_env.__file__, script)
        # Set the child umask without changing the test runner's process-wide mask.
        return subprocess.run(
            [sys.executable, "-c", "import os, runpy, sys; "
             "os.umask(int(sys.argv[1], 8)); runpy.run_path(sys.argv[2], run_name='__main__')",
             umask, str(script)],
            check=True, capture_output=True, text=True,
        )

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits do not establish Windows ACLs")
    def test_new_credentials_are_private_even_with_permissive_umask(self):
        for umask in ("022", "000"):
            with self.subTest(umask=umask), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                result = self.run_generator(root, umask)
                target = root / ".env"
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                lines = target.read_text().splitlines()
                self.assertEqual(len(lines), 2)
                for name, line in zip(("CU_DB_ROOT_PASSWORD", "CU_DB_PASSWORD"), lines):
                    self.assertRegex(line, "^" + name + "=[0-9a-f]{64}$")
                    self.assertNotIn(line.split("=", 1)[1], result.stdout + result.stderr)

    @unittest.skipUnless(os.name == "posix", "POSIX mode bits do not establish Windows ACLs")
    def test_file_is_already_private_before_credentials_are_written(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".env"

            def generate(length):
                self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
                return "a" * (length * 2)

            previous_umask = os.umask(0)
            try:
                with patch.object(init_env, "__file__", str(root / "scripts" / "init_env.py")), \
                        patch.object(init_env.secrets, "token_hex", side_effect=generate) as tokens, \
                        contextlib.redirect_stdout(io.StringIO()):
                    init_env.main()
                self.assertEqual(tokens.call_count, 2)
            finally:
                os.umask(previous_umask)

    def test_existing_credentials_and_permissions_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".env"
            original = b"CU_DB_ROOT_PASSWORD=existing-root\nCU_DB_PASSWORD=existing-app\n"
            target.write_bytes(original)
            if os.name == "posix":
                target.chmod(0o640)
            previous_mode = stat.S_IMODE(target.stat().st_mode)
            result = self.run_generator(root)
            self.assertEqual(target.read_bytes(), original)
            self.assertEqual(stat.S_IMODE(target.stat().st_mode), previous_mode)
            self.assertIn("keeping existing credentials", result.stdout)
            self.assertNotIn("existing-root", result.stdout + result.stderr)
            self.assertNotIn("existing-app", result.stdout + result.stderr)

    @unittest.skipUnless(os.name == "posix", "Symlink creation requires extra Windows privileges")
    def test_existing_and_dangling_symlinks_are_not_followed_or_replaced(self):
        for dangling in (False, True):
            with self.subTest(dangling=dangling), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                destination = root / "preserve"
                if not dangling:
                    destination.write_bytes(b"existing secret data\n")
                target = root / ".env"
                target.symlink_to(destination)
                result = self.run_generator(root)
                self.assertTrue(target.is_symlink())
                self.assertEqual(target.readlink(), destination)
                if dangling:
                    self.assertFalse(destination.exists())
                else:
                    self.assertEqual(destination.read_bytes(), b"existing secret data\n")
                self.assertIn("keeping existing credentials", result.stdout)
                self.assertNotIn("existing secret data", result.stdout + result.stderr)

    def test_creation_error_propagates_without_generating_or_printing_credentials(self):
        output = io.StringIO()
        with patch.object(init_env.os, "open", side_effect=PermissionError("creation denied")), \
                patch.object(init_env.secrets, "token_hex") as generate, \
                contextlib.redirect_stdout(output):
            with self.assertRaisesRegex(PermissionError, "creation denied"):
                init_env.main()
        generate.assert_not_called()
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
