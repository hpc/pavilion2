import copy
import time

from pavilion import commands
from pavilion.output import fprint
from pavilion.plugins.commands import status
from pavilion.status_file import STATES
from pavilion.test_run import TestRun


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
            help='Maximum time to wait for results in seconds. Default is to'
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
            '-s', '--silent', action='store_true',
            help="No periodic status output."
        )
        group.add_argument(
            '--oneline', action='store_true',
            help="Prints entire status on one line."
        )

    def run(self, pav_cfg, args):

        # get start time
        start_time = time.time()

        tests = status.get_tests(pav_cfg, args, self.errfile)

        # determine timeout time, if there is one
        end_time = None
        if args.timeout is not None:
            end_time = start_time + float(args.timeout)

        periodic_status_count = 0
        while (len(tests) != 0) and (end_time is None or
                                     time.time() < end_time):
            # Check which tests have completed or failed and move them to the
            # final list.
            temp_tests = copy.deepcopy(tests)
            for test_id in temp_tests:
                test_obj = TestRun.load(pav_cfg, test_id)
                run_complete_file = test_obj.path/'RUN_COMPLETE'
                if run_complete_file.exists():
                    tests.remove(test_id)

            # print status every 5 seconds
            if not args.silent:
                if time.time() > (start_time + 5*periodic_status_count):
                    stats = status.get_statuses(pav_cfg, args, self.errfile)
                    stats_out = []

                    if not args.oneline:
                        for test in stats:
                            stat = [str(time.ctime(time.time())), ':',
                                    'test #',
                                    str(test['test_id']),
                                    test['name'],
                                    test['state'],
                                    test['note'],
                                    "\n"]
                            stats_out.append(' '.join(stat))
                        fprint(''.join(map(str, stats_out)),
                               file=self.outfile, width=None)
                    else:
                        stats_out.extend([
                            str(time.ctime(time.time())), ': '
                        ])
                        for test in stats:
                            stat = [str(test['test_id']),
                                    '(', test['name'], ') ',
                                    test['state'], ' | ']
                            stats_out.append(''.join(stat))
                        fprint(''.join(map(str, stats_out)), end='\r',
                               file=self.outfile, width=None)

                    periodic_status_count += 1

        final_stats = status.get_statuses(pav_cfg, args, self.errfile)
        fprint('\n', file=self.outfile)
        return status.print_status(final_stats, self.outfile, args.json)
