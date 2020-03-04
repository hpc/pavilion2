import time
import sys

from pavilion import commands
from pavilion.plugins.commands import status
from pavilion.status_file import STATES
from pavilion.output import fprint


class WaitCommand(commands.Command):

    def __init__(self):
        super().__init__('wait', 'Wait for the specified test or series to '
                         'complete or fail and return the status.',
                         short_help="Wait for statuses of tests.")

        self.comp_list = [STATES.CREATION_ERROR,
                          STATES.SCHED_ERROR,
                          STATES.SCHED_CANCELLED,
                          STATES.BUILD_FAILED,
                          STATES.BUILD_TIMEOUT,
                          STATES.BUILD_ERROR,
                          STATES.ENV_FAILED,
                          STATES.RUN_TIMEOUT,
                          STATES.RUN_ERROR,
                          STATES.RESULTS_ERROR,
                          STATES.COMPLETE]

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            '-t', '--timeout', action='store',
            help='Maximum time to wait for results in seconds. Default=60.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to check.  These may be any mix of '
                 'test IDs and series IDs.  If no value is provided, the most '
                 'recent series submitted by this user is checked.'
        )
        parser.add_argument(
            '-s', '--silent', action='store_true'
        )

    def run(self, pav_cfg, args):
        start_time = time.time()

        tmp_statuses = status.get_statuses(pav_cfg, args, self.errfile)

        final_statuses = 0

        # determine timeout time, if there is one
        end_time = None
        if args.timeout is not None:
            end_time = start_time + float(args.timeout)

        periodic_status_count = 0
        while (final_statuses < len(tmp_statuses) and (end_time is None or
                                                       time.time() < end_time)):
            # Check which tests have completed or failed and move them to the
            # final list.
            final_statuses = 0
            for test in tmp_statuses:
                if test['state'] in self.comp_list:
                    final_statuses += 1

            tmp_statuses = status.get_statuses(pav_cfg, args, self.errfile)

            # print status every 5 seconds
            if not args.silent:
                if time.time() > (start_time + 5*periodic_status_count):
                    for test in tmp_statuses:
                        stat = [str(time.ctime(time.time())), ':',
                                str(test['test_id']),
                                test['name'],
                                test['state'],
                                test['note']]
                        fprint(' '.join(stat))
                    periodic_status_count += 1

        ret_val = status.print_status(tmp_statuses, self.outfile, args.json)

        return ret_val
