"""Prints files from a given test run id."""

import errno
import os
import sys

from pavilion import dir_db
from pavilion import output
from pavilion import cmd_utils
from pavilion.test_ids import TestID
from .base_classes import Command


class CatCommand(Command):
    """Prints the given file for a given test run id."""

    def __init__(self):
        super().__init__(
            'cat',
            'Print the contents of a pav <job id> file.',
            short_help="Print file information of <job id>"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'test_id', help="test id",
            nargs='?', default=None,
            metavar='TEST_ID'
        )
        parser.add_argument(
            'file',
            help="filename",
            metavar='FILE',
            type=str,
        )

    def run(self, pav_cfg, args):
        """Run this command."""

        if args.test_id is None:
            test_id = cmd_utils.get_last_test_id(pav_cfg, self.errfile)

            if test_id is None:
                output.fprint(self.errfile, "No last test found.", color=output.RED)
                return 1
        elif TestID.is_valid_id(args.test_id):
            test_id = TestID(args.test_id)
        else:
            output.fprint(self.errfile, f"{args.test_id} is not a valid test ID.")
            return errno.EEXIST

        tests = cmd_utils.get_tests_by_id(pav_cfg, [test_id], self.errfile)
        if not tests:
            output.fprint(self.errfile, "Could not find test '{}'".format(test_id))
            return errno.EEXIST
        elif len(tests) > 1:
            output.fprint(
                self.errfile, "Matched multiple tests. Printing file contents for first "
                              "test only (test {})".format(tests[0].full_id),
                color=output.YELLOW)

        test = tests[0]
        if not test.path.is_dir():
            output.fprint(sys.stderr, "Directory '{}' does not exist."
                          .format(test.path.as_posix()), color=output.RED)
            return errno.EEXIST

        if not test.path/args.file:
            output.fprint(sys.stderr, "File {} does not exist for test {}."
                                      .format(args.file, test.full_id))
            return errno.EEXIST

        return self.print_file(test.path / args.file)

    def print_file(self, file):
        """Print the file at the given path.
        :param path file: The path to the file to print.
        """

        try:
            with file.open() as file:
                while True:
                    block = file.read(4096)
                    if not block:
                        break
                    output.fprint(self.outfile, block, width=None, end="")
                output.fprint(self.outfile, '')

        except FileNotFoundError:
            output.fprint(sys.stderr, "file '{}' does not exist.".format(file), color=output.RED)
            return errno.EEXIST

        except IsADirectoryError:
            output.fprint(sys.stderr, "{} is a directory.".format(file), color=output.RED)
            return errno.EINVAL

        except (IOError, OSError, PermissionError) as err:
            output.fprint(sys.stdout, "Error opening file '{}'".format(file), err,
                          color=output.RED)
            return errno.EIO
