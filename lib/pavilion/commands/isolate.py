from argparse import ArgumentParser, Namespace, Action
from pathlib import Path
import shutil
import tarfile
import sys
from typing import Dict, Any, Optional

from pavilion import output
from pavilion.config import PavConfig
from pavilion.test_run import TestRun
from pavilion.test_ids import TestID
from pavilion.cmd_utils import get_last_test_id, get_tests_by_id, list_files
from .base_classes import Command


class IsolateCommand(Command):
    """Isolates an existing test run in a form that can be run without Pavilion."""

    IGNORE_FILES = ("series", "job")

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

        return self._isolate(test, args.path, args.archive, args.zip)

    @classmethod
    def _isolate(cls, test: TestRun, dest: Path, archive: bool, zip: bool) -> int:
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
            if zip:
                archive_format = "gztar"
            else:
                archive_format = "tar"

            try:
                with tarfile.open(dest, "w:gz") as tf:
                    for f in list_files(test.path, include_root=True):
                        if f.name not in cls.IGNORE_FILES:
                            print(f.relative_to(test.path.parent))
                            tf.add(f, arcname=f.relative_to(test.path.parent), recursive=False)
            except Exception as err:
                output.fprint(
                    sys.stderr,
                    f"Unable to isolate test {test.id} at {dest}: {err}",
                    color=output.RED)

                return 7
        else:
            try:
                shutil.copytree(test.path, dest, ignore=lambda x, y: cls.IGNORE_FILES)
            except OSError:
                output.fprint(
                    sys.stderr,
                    f"Unable to isolate test {test.id} at {dest}.",
                    color=output.RED)

                return 8

        return 0