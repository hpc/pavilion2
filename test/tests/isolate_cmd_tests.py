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


class IsolateCmdTests(PavTestCase):

    def test_no_archive(self):
        run_cmd = commands.get_command("run")
        isolate_cmd = commands.get_command("isolate")

        run_cmd.silence()
        isolate_cmd.silence()

        parser = arguments.get_parser()
        run_args = ["run", "-H", "this", "hello_world.hello"]

        run_cmd.run(self.pav_cfg, parser.parse_args(run_args))
        last_test = next(iter(run_cmd.last_tests))

        with tempfile.TemporaryDirectory() as dir:
            isolate_args = parser.parse_args(["isolate", str(Path(dir) / "dest")])

            self.assertEqual(isolate_cmd.run(self.pav_cfg, isolate_args), 0)

            source_files = set(list_files(last_test.path))
            dest_files = set(list_files(Path(dir) / "dest"))

            self.assertFalse(any(map(lambda x: x.is_symlink(), dest_files)))
            self.assertEqual({f for f in source_files if f not in ("series", "job")}, dest_files)

    def test_zip_archive(self):
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

                    dest_files = list_files(Path(extract_dir))

                    self.assertFalse(any(map(lambda x: x.is_symlink(), dest_files)))

                    source_files = set(map(
                                        lambda x: Path(x).relative_to(last_test.path.parent),
                                        list_files(last_test.path, include_root=True)))
                    dest_files = set(dest_files)

                    self.assertEqual(
                        {f for f in source_files if f.name not in ("series", "job")},
                        dest_files)