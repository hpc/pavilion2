from argparse import ArgumentParser, Namespace, Action
from pathlib import Path
import tarfile
import sys

from pavilion import output
from pavilion import schedulers
from pavilion.config import PavConfig
from pavilion.test_run import TestRun
from pavilion.test_ids import TestID
from pavilion.cmd_utils import get_last_test_id, get_tests_by_id, list_files
from pavilion.utils import copytree_resolved
from pavilion.schedulers.config import validate_config
from .base_classes import Command


class IsolateCommand(Command):
    """Isolates an existing test run in a form that can be run without Pavilion."""

    IGNORE_FILES = ("series",)
    KICKOFF_FN = "kickoff.isolated"

    def __init__(self):
        super().__init__(
            "isolate",
            "Isolate an existing test run.",
            short_help="Isolate a test run."
        )

    def _setup_arguments(self, parser: ArgumentParser) -> None:
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
    def _isolate(cls, pav_cfg: PavConfig, test: TestRun, dest: Path, archive: bool, zip: bool) -> int:
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
            self._write_tarball(test.id, test.path, dest, zip, cls.IGNORE_FILES)

        else:
            try:
                copytree_resolved(test.path, dest, ignore_files=cls.IGNORE_FILES)
            except OSError as err:
                output.fprint(
                    sys.stderr,
                    f"Unable to isolate test {test.id} at {dest}: {err}",
                    color=output.RED)

                return 8

            cls._write_kickoff_script(pav_cfg, test, dest / cls.KICKOFF_FN)

        return 0

    @classmethod
    def _write_tarball(cls, pav_cfg: PavConfig, test_id: TestID, src: Path, dest: Path, zip: bool,
                        ignore_files) -> None:
        if zip:
            if len(dest.suffixes) == 0:
                dest = dest.with_suffix(".tgz")

            modestr = "w:gz"
        else:
            if len(dest.suffixes) == 0:
                dest = dest.with_suffix(".tar")

            modestr = "w:"

        with tempfile.TemporaryDirectory() as tmp:
            utils.copytree_resolved(src, tmp, ignore_files=ignore_files)
            cls._write_kickoff_script(pav_cfg, test_id, tmp / cls.KICKOFF_FN)

            try:
                with tarfile.open(dest, modestr) as tarf:
                    for fname in list_files(tmp):
                        tarf.add(
                                fname,
                                arcname=fname.relative_to(src.parent),
                                recursive=False)
            except (tarfile.TarError, OSError):
                output.fprint(
                    sys.stderr,
                    f"Unable to isolate test {test_id} at {dest}.",
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

        script = sched._get_kickoff_script_header(
                                            job_name="pav_{test.name}_isolated",
                                            sched_config=validate_config(test.config['schedule']),
                                            nodes=None,
                                            node_range=None,
                                            shebang=test.shebang
                                            )

        script.write(script_path)
