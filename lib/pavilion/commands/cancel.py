"""Cancels tests as prescribed by the user."""

import errno
import time

from pavilion import cancel_utils
from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import series
from pavilion.errors import TestSeriesError
from pavilion.test_run import TestRun
from .base_classes import Command
from ..errors import TestRunError


class CancelCommand(Command):
    """Cancel a set of commands using the appropriate scheduler."""

    def __init__(self):
        super().__init__(
            'cancel',
            'Cancel a test, tests, or all tests in a test series. To cancel a series '
            'itself, use `pav series cancel`. Tests can only be cancelled on the system '
            'where they were started.',
            short_help="Cancel a test, tests, or all tests in a test series."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-s', '--status', action='store_true', default=False,
            help='Prints status of cancelled jobs.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to cancel. These may be any mix of '
                 'test IDs and series IDs. If no value is provided, all test '
                 'in the most recent series submitted by the user is cancelled.')
        filters.add_test_filter_args(parser, sort_keys=[], disable_opts=['sys-name'])

    def run(self, pav_cfg, args):
        """Cancel the given tests."""

        if not args.tests:
            # Get the last series ran by this user.
            series_id = series.load_user_series_id(pav_cfg)
            if series_id is not None:
                args.tests.append(series_id)

        cancelled_series = False

        test_paths = cmd_utils.arg_filtered_tests(pav_cfg, args).paths

        tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, errfile=self.errfile)

        return cancel_utils.cancel_tests(pav_cfg, tests, self.outfile)
