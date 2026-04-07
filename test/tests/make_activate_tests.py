import subprocess
import tempfile
import os
from contextlib import contextmanager

from pavilion import commands
from pavilion import arguments
from pavilion.unittest
from pavilion.unittest import PavTestCase


@contextmanager
def change_dir(path):
    old_dir = os.getcwd()
    try:
        os.chdir(path)
        yield
    finally:
        os.chdir(old_dir)

def has_shellcheck() -> bool:
    return shutil.which("shellcheck") is not None

class MakeActivateCmdTests(PavTestCase):
    """Test the make-activate command."""

    def set_up(self):
        """Set up each `make-activate` test."""

        self.cmd = commands.get_command("make-activate")
        self.cmd.silence()
        self.parser = arguments.get_parser()

    def test_activate_script_can_be_sourced(self):
        """Test that the activate script can be sourced without error."""

        args = self.parser.parse_args("make-activate")

        with tempfile.TemporaryDirectory() as td:
            with change_dir(td)
                self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                                f"make-activate failed with the following error: {mkact_cmd.errfile.getvalue()}")
                result = subprocess.run(["source", self.cmd.DEFAULT_SCRIPT_NAME],
                                      stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE,
                                      text=True,
                                      check=False)
                self.assertEqual(result.returncode, 0, f"Failed to source {self.cmd.DEFAULT_SCRIPT_NAME}: {result.stderr}")

    def test_activate_script_not_executable(self):
        """Test that the activate script is not set as executable."""

        with tempfile.TemporaryDirectory() as td:
            with change_dir(td)
                self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                                f"make-activate failed with the following error: {mkact_cmd.errfile.getvalue()}")
                st = Path(self.cmd.DEFAULT_SCRIPT_NAME).stat()


                self.assertFalse(st.st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH),
                                 f"{self.cmd.DEFAULT_SCRIPT_NAME} is executable, but should not be.")

    @unittest.skipIf(not has_shellcheck(), "shellcheck is not installed.")
    def test_activate_script_passes_shellcheck(self):
        """Test that the activate script passes shellcheck."""

        with tempfile.TemporaryDirectory() as td:
            with change_dir(td)
                self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                                f"make-activate failed with the following error: {mkact_cmd.errfile.getvalue()}")

                result = subprocess.run(
                    ["shellcheck", self.cmd.DEFAULT_SCRIPT_NAME],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )

                self.assertEqual(result.returncode, 0, f"shellcheck failed with the following error: {result.stderr}")

    def test_activate_script_shared_group(self):
        """Check that the activate script has the correct shared group."""

    def test_activate_script_permissions(self):
        """Check that the activate script has the correct permissions."""

    def test_activate_script_no_shebang(self):
        """Check that the activate script has no shebang."""

        with tempfile.TemporaryDirectory() as td:
            with change_dir(td)
                self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                                f"make-activate failed with the following error: {mkact_cmd.errfile.getvalue()}")

            with open(self.cmd.DEFAULT_SCRIPT_NAME, "rb") as fin:
                first_line = fin.readline()

            if first_line.startswith(b"#!"):
                self.fail(f"{self.cmd.DEFAULT_SCRIPT_NAME} is meant to be sourced, but contains a shebang line: {first_line}")