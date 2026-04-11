import subprocess
import tempfile
import os
import unittest
import shutil
from pathlib import Path

from pavilion import commands
from pavilion import arguments
from pavilion.unittest import PavTestCase


class MakeActivateCmdTests(PavTestCase):
    """Test the make-activate command."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.pav_src_dir = Path(__file__).parents[2]

    def set_up(self):
        """Set up each `make-activate` test."""

        self.cmd = commands.get_command("make-activate")
        self.cmd.silence()
        self.parser = arguments.get_parser()
        self._temp_dir = tempfile.TemporaryDirectory()
        self._old_dir = os.getcwd()
        os.chdir(self._temp_dir.name)

    def tear_down(self):
        """Tear down each `make-activate` test."""

        os.chdir(self._old_dir)
        self._temp_dir.cleanup()

    def test_activate_script_can_be_sourced(self):
        """Test that the activate script can be sourced without error."""

        args = self.parser.parse_args(["make-activate"])

        self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                        f"make-activate failed with the following error: {self.cmd.errfile.getvalue()}")

        Path(self.pav_src_dir.stem).symlink_to(self.pav_src_dir)

        bash_cmd = f"source {self.cmd.DEFAULT_SCRIPT_NAME}"

        result = subprocess.run(["bash", "-c", bash_cmd],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=False)

        self.assertEqual(result.returncode, 0, f"Failed to source {self.cmd.DEFAULT_SCRIPT_NAME}: {result.stderr}")

    def test_activate_script_shared_group(self):
        """Check that the activate script has the correct shared group."""

    def test_activate_script_permissions(self):
        """Check that the activate script has the correct permissions."""

    def test_activate_script_no_shebang(self):
        """Check that the activate script has no shebang."""

        args = self.parser.parse_args(["make-activate"])

        self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                        f"make-activate failed with the following error: {self.cmd.errfile.getvalue()}")

        first_line = ""

        with open(self.cmd.DEFAULT_SCRIPT_NAME, "rb") as fin:
            first_line = fin.readline()

        if first_line.startswith(b"#!"):
            self.fail(f"{self.cmd.DEFAULT_SCRIPT_NAME} is meant to be sourced, but contains a shebang line: {first_line}")

    def test_make_activate_does_not_overwrite_existing_scripts(self):
        """Check that make-activate will refuse to overwrite an existing activate script."""

        args = self.parser.parse_args(["make-activate"])

        expected = "This is the old activate script."

        with open(self.cmd.DEFAULT_SCRIPT_NAME, "w") as fout:
            fout.write(expected)

        self.assertNotEqual(self.cmd.run(self.pav_cfg, args), 0,
                        f"make-activate ran successfully, but should have exited with a non-zero error code.")

        script_contents = ""

        with open(self.cmd.DEFAULT_SCRIPT_NAME, "r") as fin:
            script_contents = fin.read()

        self.assertEqual(script_contents, expected, f"{self.cmd.DEFAULT_SCRIPT_NAME} was overwritten by make-activate.")

        errors = self.cmd.errfile.getvalue()

        self.assertNotEqual(errors, "", "pav make-activate should have printed an error message, but did not.")

    def test_activate_script_sets_correct_env_variables(self):
        """Test that the activate script sets the correct environment variables."""

        args = self.parser.parse_args(["make-activate"])

        self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                         f"make-activate failed with the following error: {self.cmd.errfile.getvalue()}")

        Path(self.pav_src_dir.stem).symlink_to(self.pav_src_dir)

        bash_cmd = f"source {self.cmd.DEFAULT_SCRIPT_NAME} >/dev/null && echo \"$PAVBIN\" && echo \"$PAV_CONFIG_DIR\""

        result = subprocess.run(["bash", "-c", bash_cmd],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=False)

        self.assertEqual(result.returncode, 0, f"Failed to source {self.cmd.DEFAULT_SCRIPT_NAME}: {result.stderr}")

        output = result.stdout
        pav_bin_out = Path(result.stdout.splitlines()[0].strip()).resolve()
        pav_config_out = Path(result.stdout.splitlines()[1].strip()).resolve()

        self.assertEqual(pav_bin_out, self.pav_src_dir / "bin",
                            f"{self.cmd.DEFAULT_SCRIPT_NAME} did not correctly set PAVBIN. "
                            f"Got value: {pav_bin_out}.")

        self.assertEqual(Path(".").resolve(), pav_config_out,
                            f"{self.cmd.DEFAULT_SCRIPT_NAME} did not correctly set "
                            f"PAV_CONFIG_DIR. Got value: {pav_config_out}.")

    def test_activate_script_sources_cd_command(self):
        """Check that the activate script activates the cd command by sourcing `cd.sh`."""

        args = self.parser.parse_args(["make-activate"])

        self.assertEqual(self.cmd.run(self.pav_cfg, args), 0,
                        f"make-activate failed with the following error: {self.cmd.errfile.getvalue()}")

        Path(self.pav_src_dir.stem).symlink_to(self.pav_src_dir)

        # bash_cmd = f"set -x; source {self.cmd.DEFAULT_SCRIPT_NAME}; echo status=$?; declare -F pav"
        bash_cmd = f"source {self.cmd.DEFAULT_SCRIPT_NAME} && declare -F pav"

        result = subprocess.run(["bash", "-c", bash_cmd],
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                universal_newlines=True,
                                check=False)

        self.assertEqual(result.returncode, 0, f"{self.cmd.DEFAULT_SCRIPT_NAME} did not correctly source cd.sh. "
                         "Expected pav to be a function, but it is a not.")

    def test_make_activate_properly_handles_spaces(self):
        """Check that the make-active command properly handles spaces in file and directory names."""