"""The Status command, along with useful functions that make it easy for
other commands to print statuses."""

import errno

from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import status_utils
from .base_classes import Command


class StatusCommand(Command):
    """Prints the status of a set of tests."""

    def __init__(self):
        super().__init__('status', 'Check the status of a test, list of tests,'
                                   ' or test series. You may also specify "all" as '
                                   'the test id, to get the status of all tests. The '
                                   'default "all" filter gives your recent tests, but setting '
                                   'any filter argumument overrides that.',
                         short_help="Get status of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            '--series', action='store_true', default=False,
            help='Show the series the test belongs to.')
        parser.add_argument(
            '--note', action='store_true', default=False,
            help='Show the status note.')
        parser.add_argument(
            'tests', nargs='*', action='store',
            help="The name(s) of the tests to check.  These may be any mix of "
                 "test IDs and series IDs. Lists tests in the last series you "
                 "ran by default. Use 'all' to show all tests."
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
        try:
            test_paths = cmd_utils.arg_filtered_tests(pav_cfg, args, verbose=self.errfile).paths
        except ValueError as err:
            output.fprint(self.errfile, err, color=output.RED)
            return errno.EINVAL

        if args.history:
            tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, self.errfile)
            if len(tests) != 1:
                output.fprint(self.errfile, "'--history' flag requires a single test id, "
                                            "got: {}"
                              .format(len(test_paths)), color=output.RED)
                return 1
            return status_utils.print_status_history(tests[-1], self.outfile, args.json)

        tests = cmd_utils.get_tests_by_paths(pav_cfg, test_paths, self.errfile)

        statuses = status_utils.get_statuses(pav_cfg, tests)
        if args.summary:
            return self.print_summary(statuses)
        else:
            return status_utils.print_status(statuses, self.outfile, json=args.json,
                                             series=args.series, note=args.note)

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

        rows.sort(key=lambda status: status['State'])

        output.draw_table(outfile=self.outfile,
                          field_info=field_info,
                          fields=fields,
                          rows=rows,
                          border=True,
                          title='Test Summary')

        return ret_val
