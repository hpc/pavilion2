import sys
import time

from pavilion import commands
from pavilion.plugins.commands import status
from pavilion.status_file import STATES


class WaitCommand(commands.Command):

    def __init__(self):
        super().__init__('wait', 'Wait for the specified test or series to '
                         'complete or fail and return the status.',
                         short_help="Wait for statuses of tests.")

        self.comp_list = [STATES.CREATION_ERROR,
                          STATES.SCHED_ERROR,
                          STATES.SCHED_CANCELLED,
                          STATES.BUILD_FAILED,
                          STATES.BUILD_ERROR,
                          STATES.ENV_FAILED,
                          STATES.RUN_TIMEOUT,
                          STATES.RUN_FAILED,
                          STATES.RUN_ERROR,
                          STATES.RESULTS_ERROR,
                          STATES.COMPLETE]

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            '-t', '--timeout', action='store', default='60',
            help='Maximum time to wait for results in seconds. Default=60.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to check.  These may be any mix of '
                 'test IDs and series IDs.  If no value is provided, the most '
                 'recent series submitted by this user is checked.'
        )

    def run(self, pav_cfg, args):
        # Store the initial time for timeout functionality.
        start_time = time.time()

        tmp_statuses = status.get_statuses(pav_cfg, args, self.errfile)

        final_statuses = 0

        while (final_statuses < len(tmp_statuses)) and \
              ((time.time() - start_time) < float(args.timeout)):
            # Check which tests have completed or failed and move them to the
            # final list.
            final_statuses = 0
            for test in tmp_statuses:
                if test['state'] in self.comp_list:
                    final_statuses += 1

            tmp_statuses = status.get_statuses(pav_cfg, args, self.errfile)

        ret_val = status.print_status(tmp_statuses, self.outfile, args.json)

        return ret_val
