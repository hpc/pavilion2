"""Wait for the specified tests to finish, printing progress reports along
the way."""

import os
import time
from typing import List

from pavilion import cmd_utils
from pavilion import commands
from pavilion import status_utils
from pavilion.output import fprint
from pavilion.status_file import STATES
from pavilion.test_run import TestRun


def check_pgid(pgid):
    """Checks if pgid still exists. Returns false if pgid does not exist."""

    try:
        # PGID needs to be negative
        if pgid > 0:
            pgid = -1*pgid

        # No signal is sent, but an OS Error will be raised if the PID doesn't
        # exist
        os.kill(pgid, 0)
    except OSError:
        return False
    else:
        return True


class WaitCommand(commands.Command):
    """A command to wait for test completion."""

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

    OUT_SILENT = 'silent'
    OUT_SUMMARY = 'summary'

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-t', '--timeout', action='store',
            help='Maximum time to wait for results in seconds. Default is to '
                 'wait indefinitely.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to check.  These may be any mix of '
                 'test IDs and series IDs.  If no value is provided, the most '
                 'recent series submitted by this user is checked.'
        )

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '-s', '--silent',
            action='store_const', dest='out_mode', const=self.OUT_SILENT,
            help="No periodic status output."
        )
        group.add_argument(
            '--summary',
            action='store_const', dest='out_mode', const=self.OUT_SUMMARY,
            help="Prints a summary of the status."
        )

    def run(self, pav_cfg, args):
        """Wait for the requested tests to complete."""

        # get start time
        start_time = time.time()
        tests = cmd_utils.get_tests_by_id(pav_cfg, args.tests, self.errfile)

        # determine timeout time, if there is one
        end_time = None
        if args.timeout is not None:
            end_time = start_time + float(args.timeout)

        self.wait(pav_cfg, tests, end_time, args.out_mode)
        return 0

    STATUS_UPDATE_PERIOD = 5  # seconds

    def wait(self, pav_cfg, tests: List[TestRun],
             end_time: float, out_mode: str) -> None:
        """Wait on each of the given tests to complete, printing a status
        message """

        done_tests = []
        all_tests = list(tests)
        all_tests.sort(key=lambda t: t.full_id)

        tests = list(tests)

        status_time = time.time() + self.STATUS_UPDATE_PERIOD
        while tests and (end_time is None or time.time() < end_time):

            for test_state in tests:
                if test_state.complete:
                    done_tests.append(test_state)
                    tests.remove(test_state)

            # print status every 5 seconds
            if time.time() > status_time:
                status_time = time.time() + self.STATUS_UPDATE_PERIOD

                stats = status_utils.get_statuses(pav_cfg, all_tests)
                stats_out = []

                if out_mode == self.OUT_SILENT:
                    pass
                elif out_mode == self.OUT_SUMMARY:
                    states = {}
                    for test_state in stats:
                        if test_state['state'] not in states.keys():
                            states[test_state['state']] = 1
                        else:
                            states[test_state['state']] += 1
                    status_counts = []
                    for state, count in states.items():
                        status_counts.append(state + ': ' + str(count))
                    fprint(' | '.join(status_counts), file=self.outfile,
                           end='\r', width=None)
                else:
                    for test_state in stats:
                        stat = [str(time.ctime(time.time())), ':',
                                'test #',
                                str(test_state['test_id']),
                                test_state['name'],
                                test_state['state'],
                                test_state['note'],
                                "\n"]
                        stats_out.append(' '.join(stat))
                    fprint(''.join(map(str, stats_out)),
                           file=self.outfile, width=None)

        final_stats = status_utils.get_statuses(pav_cfg, tests)
        fprint('\n', file=self.outfile)
        status_utils.print_status(final_stats, self.outfile)
