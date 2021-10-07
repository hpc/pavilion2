"""The Status command, along with useful functions that make it easy for
other commands to print statuses."""

import errno
from datetime import datetime

from pavilion import cmd_utils
from pavilion import commands
from pavilion import filters
from pavilion import output
from pavilion import status_utils
from pavilion.test_run import (
    TestRun, TestRunError, TestRunNotFoundError)


class StatusCommand(commands.Command):
    """Prints the status of a set of tests."""

    def __init__(self):
        super().__init__('status', 'Check the status of a test, list of tests,'
                                   ' or test series.',
                         short_help="Get status of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help="The name(s) of the tests to check.  These may be any mix of "
                 "test IDs and series IDs. Use 'last' to get just the last "
                 "series you ran."
        )
        output_mode = parser.add_mutually_exclusive_group()
        output_mode.add_argument(
            '-s', '--summary', default=False, action='store_true',
            help='Display a single line summary of test statuses.'
        )
        output_mode.add_argument(
            '--history', default=False, action='store_true',
            help='Display status history for a single test_run.'
        )

        filters.add_test_filter_args(parser)

    def run(self, pav_cfg, args):
        """Gathers and prints the statuses from the specified test runs and/or
        series."""

        test_ids = status_utils.get_tests(pav_cfg, args.tests, self.errfile)
        args.tests = list(map(str, test_ids))

        try:
            test_ids = cmd_utils.arg_filtered_tests(pav_cfg, args, verbose=self.errfile)
        except ValueError as err:
            output.fprint(err.args[0], color=output.RED, file=self.errfile)
            return errno.EINVAL

        statuses = status_utils.get_statuses(pav_cfg, test_ids)

        if args.summary:
            return self.print_summary(statuses)
        elif args.history:
            if len(test_ids) != 1:
                output.fprint("'--history' flag requires a single test id, "
                              "got: {}"
                              .format(test_ids),
                              file=self.errfile,
                              color=output.RED)
                return 1
            return status_utils.print_status_history(pav_cfg, test_ids[-1],
                                                     self.outfile, args.json)
        else:
            return status_utils.print_status(statuses, self.outfile, args.json)

    def print_summary(self, statuses):
        """Print_summary takes in a list of test statuses.
        It summarizes basic state output and displays
        the data to the user through draw_table.
        :param statuses: state list of current jobs
        :rtype: int
        """
        # Populating table dynamically requires dict

        summary_dict = {}
        passes = 0
        ret_val = 0
        total_tests = len(statuses)
        rows = []
        fields = ['State', 'Amount', 'Percent']
        fails = 0

        # Shrink statues dict to singular keys with total
        # amount of key as the value
        for test in statuses:
            if test['state'] not in summary_dict.keys():
                summary_dict[test['state']] = 1
            else:
                summary_dict[test['state']] += 1

            # Gathers info on passed tests from completed tests.
            if 'COMPLETE' in test['state'] and 'PASS' in test['note']:
                passes += 1

        if 'COMPLETE' in summary_dict.keys():
            fails = summary_dict['COMPLETE'] - passes
            fields = ['State', 'Amount', 'Percent', 'PASSED', 'FAILED']

        for key, value in summary_dict.items():
            #  Build the rows for drawtables.

            #  Determine Color.
            if key.endswith('ERROR') or key.endswith('TIMEOUT') or \
               key.endswith('FAILED') or key == 'ABORTED' or key == 'INVALID':
                color = output.RED
            elif key == 'COMPLETE':
                color = output.GREEN
            elif key == 'SKIPPED':
                color = output.YELLOW
            elif key == 'RUNNING' or key == 'SCHEDULED' \
                    or key == 'PREPPING_RUN' \
                    or key == 'BUILDING' or key == 'BUILD_DONE' \
                    or key == 'BUILD_REUSED':
                color = output.CYAN
            else:
                color = output.WHITE  # Not enough to warrant color.

            # Populating rows...
            if key == 'COMPLETE':  # only time we need to populate pass/fail
                rows.append(
                    {'State': output.ANSIString(key, color),
                     'Amount': value,
                     'Percent': '{0:.0%}'.format(value / total_tests),
                     'PASSED': '{0:.0%}'.format(passes / value)
                               + ',({}/{})'.format(passes, value),
                     'FAILED': '{0:.0%}'.format(fails / value)
                               + ',({}/{})'.format(fails, value)}
                )
            else:
                rows.append(
                    {'State': output.ANSIString(key, color),
                     'Amount': value,
                     'Percent': '{0:.0%}'.format(value / total_tests)}
                )

        field_info = {
            'PASSED': {
                'transform': lambda t: output.ANSIString(t, output.GREEN)
            },
            'FAILED': {
                'transform': lambda t: output.ANSIString(t, output.RED),
            }}

        output.draw_table(outfile=self.outfile,
                          field_info=field_info,
                          fields=fields,
                          rows=rows,
                          border=True,
                          title='Test Summary')

        return ret_val
