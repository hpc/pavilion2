import tempfile
import os
import tarfile
from pathlib import Path
import subprocess as sp
from typing import Iterator

from pavilion import commands
from pavilion import arguments
from pavilion.unittest import PavTestCase
from pavilion.cmd_utils import list_files
from pavilion.test_run import TestRun


class IsolateCmdTests(PavTestCase):

    def test_no_archive(self):
        """Test that isolating without archiving works correctly."""

        run_cmd = commands.get_command("run")
        isolate_cmd = commands.get_command("isolate")

        run_cmd.silence()
        isolate_cmd.silence()

        parser = arguments.get_parser()
        run_args = ["run", "-H", "this", "hello_world.hello"]

        run_cmd.run(self.pav_cfg, parser.parse_args(run_args))
        last_test = next(iter(run_cmd.last_tests))

        last_test.wait(timeout=self.testrun_wait_timeout)

        with tempfile.TemporaryDirectory() as dir:
            isolate_args = parser.parse_args(["isolate", str(Path(dir) / "dest")])

            self.assertEqual(isolate_cmd.run(self.pav_cfg, isolate_args), 0)

            source_files = set(map(
                                lambda x: x.relative_to(last_test.path),
                                list_files(last_test.path)))
            dest_files = set(map(
                                lambda x: x.relative_to(Path(dir) / "dest"),
                                list_files(Path(dir) / "dest")))

            self.assertIn(Path(TestRun.PAV_LIB_FN), dest_files)
            self.assertIn(Path(isolate_cmd.KICKOFF_FN), dest_files)

            self.assertEqual(
                        {f for f in source_files if f.name not in ("series", "job")},
                        {f for f in dest_files if f.name not in \
                            (TestRun.PAV_LIB_FN, isolate_cmd.KICKOFF_FN) and \
                            # Have to exclude build_origin because of how os.walk handles symlinks
                            f.parent.name != "build_origin"})

    def test_zip_archive(self):
        """Test that isolating using a compressed archive works correctly."""

        run_cmd = commands.get_command("run")
        isolate_cmd = commands.get_command("isolate")

        run_cmd.silence()
        isolate_cmd.silence()

        parser = arguments.get_parser()
        run_args = ["run", "-H", "this", "hello_world.hello"]

        run_cmd.run(self.pav_cfg, parser.parse_args(run_args))
        last_test = next(iter(run_cmd.last_tests))

        with tempfile.TemporaryDirectory() as dir:
            isolate_args = parser.parse_args(["isolate",
                                              str(Path(dir) / "dest"),
                                              "--archive",
                                              "--zip"])

            self.assertEqual(isolate_cmd.run(self.pav_cfg, isolate_args), 0)

            with tempfile.TemporaryDirectory() as extract_dir:
                with tarfile.open(Path(dir) / "dest.tgz", "r:gz") as tf:
                    tf.extractall(extract_dir)

                    source_files = set(map(
                                        lambda x: Path(x).relative_to(last_test.path),
                                        list_files(last_test.path, include_root=True)))
                    dest_files = set(map(
                                        lambda x: x.relative_to(Path(extract_dir) / "dest"),
                                        list_files(Path(extract_dir))))

                    self.assertIn(Path(TestRun.PAV_LIB_FN), dest_files)
                    self.assertIn(Path(isolate_cmd.KICKOFF_FN), dest_files)

                    self.assertEqual(
                        {f for f in source_files if f.name not in ("series", "job")},
                        {f for f in dest_files if f.name not in \
                            ("pav-lib.bash", "kickoff.isolated") and \
                            # Have to exclude build_origin because of how os.walk handles symlinks
                            f.parent.name != "build_origin"})
