"""Cancels tests as prescribed by the user."""

from pavilion import cancel_utils
from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import sys_vars
from pavilion import utils
from .base_classes import Command


class CancelCommand(Command):
    """Cancel a set of commands using the appropriate scheduler."""

    def __init__(self):
        super().__init__(
            'cancel',
            'Cancel a test, tests, or all tests in a test series. To cancel a series '
            'itself, use `pav series cancel`. Tests can only be cancelled on the system '
            'where the were started.',
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
                 'test IDs and series IDs. If no value is provided, the most '
                 'recent series submitted by the user is cancelled. '
        )
        filters.add_test_filter_args(parser, sort_keys=[], disable_opts=['sys-name'])

    def run(self, pav_cfg, args):
        """Cancel the given tests."""

        args.user = args.user or utils.get_login()
        args.sys_name = sys_vars.get_vars(defer=True).get('sys_name')

        test_paths = cmd_utils.arg_filtered_tests(pav_cfg, args, verbose=self.errfile)
        tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, errfile=self.errfile)
        output.fprint("Found {} tests to try to cancel.".format(len(tests)),
                      file=self.outfile)

        return cancel_utils.cancel_tests(pav_cfg, tests, self.outfile)
