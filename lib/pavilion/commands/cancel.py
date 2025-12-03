"""Cancels tests as prescribed by the user."""

import errno
import time
from argparse import Namespace

from pavilion import cancel_utils
from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion.series import TestSeries
from pavilion.errors import TestSeriesError
from pavilion.test_run import TestRun
from pavilion.config import PavConfig
from pavilion.test_ids import resolve_mixed_ids, SeriesID
from pavilion.micro import partition
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

    def run(self, pav_cfg: PavConfig, args: Namespace) -> int:
        """Cancel the given tests or series."""

        ids = resolve_mixed_ids(args.tests, auto_last=True)
        tests = ids["tests"]
        series = ids["series"]

        test_ret = 0
        sers_ret = 0

        if len(tests) > 0:
            test_paths = cmd_utils.arg_filtered_tests(
                                    pav_cfg,
                                    tests,
                                    series,
                                    filter_query=args.filter,
                                    limit=args.limit,
                                    verbose=self.errfile).paths
            tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, errfile=self.errfile)
            test_ret = cancel_utils.cancel_tests(pav_cfg, tests, self.outfile)
        if len(series) > 0:
            sinfos = cmd_utils.arg_filtered_series(
                                pav_cfg,
                                series,
                                verbose=self.errfile)
            test_series = list(map(lambda x: TestSeries.load(pav_cfg, x.id), sinfos))
            sers_ret = cancel_utils.cancel_series(test_series, self.outfile)

        return test_ret or sers_ret
