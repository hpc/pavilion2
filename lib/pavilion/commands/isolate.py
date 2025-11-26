from argparse import ArgumentParser, Namespace, Action
from pathlib import Path
import shutil
from typing import Dict, Any, Optional

from pavilion import output
from pavilion.config import PavConfig
from pavilion.test_ids import TestID
from pavilion.cmd_utils import get_last_test_id, get_tests_by_id
from .base_classes import Command


class ArchiveOptionsAction(Action):
    def __call__(
            parser: ArgumentParser,
            namespace: Namespace,
            values: Dict[str, Any],
            option_string: Optional[str] = None) -> None:
        if not getattr(namespace, "archive"):
            parser.error("--archive must be specified to use --zip.")
        else:
            setattr(namespace, "zip", True)


class IsolateCommand(Command):
    """Isolates an existing test run in a form that can be run without Pavilion."""

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
            action=ArchiveOptionsAction
        )

    def run(self, pav_cfg: PavConfig, args: Namespace) -> int:
        test_id = args.test_id

        if args.test_id is None:
            test_id = get_last_test_id(pav_cfg, self.errfile)

            if test_id is None:
                output.fprint(self.errfile, "No last test found.", color=output.RED)

                return 1

        tests = get_tests_by_id(pav_cfg, [test_id], self.errfile)

        if len(tests) == 0:
            output.fprint(self.errfile, "Could not find test '{}'".format(test_id))

            return 2

        elif len(tests) > 1:
            output.fprint(
                self.errfile, "Matched multiple tests. Printing file contents for first "
                              "test only (test {})".format(tests[0].full_id),
                color=output.YELLOW)

            return 3

        test = next(iter(tests))

        if not test.path.is_dir():
            output.fprint(sys.stderr, "Directory '{}' does not exist."
                          .format(test.path.as_posix()), color=output.RED)

            return 4

        if args.archive:
            if args.zip:
                archive_format = "gztar"
            else:
                archive_format = "tar"

            shutil.make_archive(args.path, archive_format, test.path)
        else:
            shutil.copytree(test.path, args.path, ignore=lambda x, y: ("series", "job"))

        return 0