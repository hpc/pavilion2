from argparse import ArgumentParser, Namespace, Action
from pathlib import Path
import tarfile
import sys
import shutil
import tempfile
from typing import Iterable

from pavilion import output
from pavilion import schedulers
from pavilion.config import PavConfig
from pavilion.test_run import TestRun
from pavilion.test_ids import TestID
from pavilion.cmd_utils import get_last_test_id, get_tests_by_id, list_files
from pavilion.utils import copytree_resolved
from pavilion.scriptcomposer import ScriptComposer
from pavilion.errors import SchedulerPluginError
from pavilion.schedulers.config import validate_config, calc_node_range
from .base_classes import Command


class IsolateCommand(Command):
    """Isolates an existing test run in a form that can be run without Pavilion."""

    IGNORE_FILES = ("series", "job")
    KICKOFF_FN = "kickoff.isolated"

    def __init__(self):
        super().__init__(
            "isolate",
            "Isolate an existing test run.",
            short_help="Isolate a test run."
        )

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        """Setup the argument parser for the isolate command."""

        parser.add_argument(
            "test_id",
            type=TestID,
            nargs="?",
            help="test ID"
            )

        parser.add_argument(
            "path",
            type=Path,
            help="isolation path"
        )

        parser.add_argument(
            "-a",
            "--archive",
            action="store_true",
            default=False,
            help="archive the test"
        )

        parser.add_argument(
            "-z",
            "--zip",
            default=False,
            help="compress the test archive",
            action="store_true"
        )

    def run(self, pav_cfg: PavConfig, args: Namespace) -> int:
        """Run the isolate command."""

        if args.zip and not args.archive:
            output.fprint(self.errfile, "--archive must be specified to use --zip.")

            return 1

        test_id = args.test_id

        if args.test_id is None:
            test_id = get_last_test_id(pav_cfg, self.errfile)

            if test_id is None:
                output.fprint(self.errfile, "No last test found.", color=output.RED)

                return 2

        tests = get_tests_by_id(pav_cfg, [test_id], self.errfile)

        if len(tests) == 0:
            output.fprint(self.errfile, "Could not find test '{}'".format(test_id))

            return 3

        elif len(tests) > 1:
            output.fprint(
                self.errfile, "Matched multiple tests. Printing file contents for first "
                              "test only (test {})".format(tests[0].full_id),
                color=output.YELLOW)

            return 4

        test = next(iter(tests))

        return self._isolate(pav_cfg, test, args.path, args.archive, args.zip)

    @classmethod
    def _isolate(cls, pav_cfg: PavConfig, test: TestRun, dest: Path, archive: bool,
                    zip: bool) -> int:
        """Given a test run and a destination path, isolate that test run, optionally
        creating a tarball."""

        if not test.path.is_dir():
            output.fprint(sys.stderr, "Directory '{}' does not exist."
                          .format(test.path.as_posix()), color=output.RED)

            return 5

        if dest.exists():
            output.fprint(
                sys.stderr,
                f"Unable to isolate test {test.id}. Destination {dest} already exists.",
                color=output.RED)

            return 6

        if archive:
            cls._write_tarball(pav_cfg,
                                test,
                                dest,
                                zip,
                                cls.IGNORE_FILES)

        else:
            try:
                copytree_resolved(test.path, dest, ignore_files=cls.IGNORE_FILES)
            except OSError as err:
                output.fprint(
                    sys.stderr,
                    f"Unable to isolate test {test.id} at {dest}: {err}",
                    color=output.RED)

                return 8

            pav_lib_bash = pav_cfg.pav_root / 'bin' / TestRun.PAV_LIB_FN
            shutil.copyfile(pav_lib_bash, dest / TestRun.PAV_LIB_FN)

            cls._write_kickoff_script(pav_cfg, test, dest / cls.KICKOFF_FN)

        return 0

    @classmethod
    def _write_tarball(cls, pav_cfg: PavConfig, test: TestRun, dest: Path, zip: bool,
                        ignore_files: Iterable[str]) -> None:
        """Given a test run object, create a tarball of its run directory in the specified
        location."""

        if zip:
            if len(dest.suffixes) == 0:
                dest = dest.with_suffix(".tgz")

            modestr = "w:gz"
        else:
            if len(dest.suffixes) == 0:
                dest = dest.with_suffix(".tar")

            modestr = "w:"

        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            tmp_dest = tmp / dest.stem
            tmp_dest.mkdir()
            copytree_resolved(test.path, tmp_dest, ignore_files=ignore_files)

            # Copy Pavilion bash library into tarball
            pav_lib_bash = pav_cfg.pav_root / 'bin' / TestRun.PAV_LIB_FN
            shutil.copyfile(pav_lib_bash, tmp_dest / TestRun.PAV_LIB_FN)

            cls._write_kickoff_script(pav_cfg, test, tmp_dest / cls.KICKOFF_FN)

            try:
                with tarfile.open(dest, modestr) as tarf:
                    for fname in list_files(tmp):
                        tarf.add(
                                fname,
                                arcname=fname.relative_to(tmp),
                                recursive=False)
            except (tarfile.TarError, OSError):
                output.fprint(
                    sys.stderr,
                    f"Unable to isolate test {test.id} at {dest}.",
                    color=output.RED)

                return 7

    @classmethod
    def _write_kickoff_script(cls, pav_cfg: PavConfig, test: TestRun, script_path: Path) -> None:
        """Write a special kickoff script that can be used to run the given test independently of
        Pavilion."""

        try:
            sched = schedulers.get_plugin(test.scheduler)
        except SchedulerPluginError:
            output.fprint(
                sys.stderr,
                f"Unable to generate kickoff script for test {test_id}: unable to load scheduler"
                f" {test.scheduler}."
            )
            return 9

        sched_config = validate_config(test.config['schedule'])
        node_range = calc_node_range(sched_config, sched_config['cluster_info']['node_count'])

        script = sched.create_kickoff_script(
                                        pav_cfg,
                                        test,
                                        isolate=True)

        script.write(script_path)
