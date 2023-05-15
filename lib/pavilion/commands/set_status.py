"""Set the status for a test run. Typically used by pavilion when a test run
errors inside its run script."""

import errno

from pavilion import cmd_utils
from pavilion import output
from pavilion.status_file import STATES
from .base_classes import Command


class SetStatusCommand(Command):
    """Plugin for setting the status of a test."""

    def __init__(self):

        super().__init__(
            'set_status',
            'Set the status of a test, list of tests, or test suite.',
            aliases=['status_set'],
            short_help="Set status of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-s', '--state', action='store', default=STATES.RUN_USER,
            help='State to set for the test, tests, or suite of tests.'
        )
        parser.add_argument(
            '-n', '--note', action='store', default="",
            help='Note to set for the test, tests, or suite of tests.'
        )
        parser.add_argument(
            'test', action='store', metavar='<test_id>',
            help='The name of the test to set the status of. If no value is '
                 'provided, the most recent suite submitted by this user is '
                 'used.'
        )

    def run(self, pav_cfg, args):
        """Set the status of the given test."""

        # Zero is given as the default when running test scripts outside of
        # Pavilion.
        if args.test == 0:
            return 0

        tests = cmd_utils.get_tests_by_id(pav_cfg, [args.test], self.errfile)

        if not tests:
            output.fprint(self.errfile, "Test {} could not be opened.".format(args.test),
                          color=output.RED)
            return errno.EINVAL

        test = tests[0]
        test.status.set(args.state, args.note)

        return 0
