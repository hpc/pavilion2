from pavilion import commands
from pavilion import schedulers
from pavilion import status_file
from pavilion import utils
from pavilion import series
from pavilion.status_file import STATES
from pavilion.pav_test import PavTest, PavTestError, PavTestNotFoundError
from pavilion.plugins.commands.status import print_from_test_obj
import errno
import sys
import argparse

class CancelCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'cancel',
            'Cancel a test, tests, or test series.',
            short_help = "Cancel a test, tests, or test series."
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-s', '--status', action='store_true', default=False,
            help='Prints status of cancelled jobs.'
        )
        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Prints status of cancelled jobs in json format.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to cancel. These may be any mix of '
                 'test IDs and series IDs. If no value is provided, the most '
                 'recent series submitted by the user is cancelled. '
        )

    def run(self, pav_cfg, args):

        if not args.tests:
            # Get the last series ran by this user. 
            series_id = series.TestSeries.load_user_series_id()
            if series_id is not None:
                args.tests.append('s{}'.format(series_id))

        test_list = []
        for test_id in args.tests:
            if test_id.startswith('s'):
                try:
                    test_list.extend(series.TestSeries.from_id(pav_cfg,int(test_id[1:])).tests)
                except series.TestSeriesError as err:
                    utils.fprint(
                        "Suite {} could not be found.\n{}".format(test_id[1:],
                                err), file=self.errfile, color=utils.RED
                    )
                except ValueError as err:
                    utils.fprint(
                        "Suite {} is not a valid suite.\n{}"
                        .format(test_id[1:], err), file=self.errfile, color=utils.RED
                    )
                    continue
            else:
                try:
                    test_list.append(int(test_id))
                except ValueError as err:
                    utils.fprint(
                        "Test {} is not a valid test.\n{}".format(test_id,
                                err), file=self.errfile, color=utils.RED
                    )
                    continue

        # Will only run if tests list is not empty. 
        if test_list:
            update_list = []
            for test_id in test_list:
                try:
                    test = PavTest.load(pav_cfg, test_id)
                    update_list.append(test)
                    sched = schedulers.get_scheduler_plugin(test.scheduler)

                    stat = test.status.current()
                    # Won't try to cancel a completed job or a job that was 
                    # previously cancelled. 
                    if stat.state != STATES.COMPLETE and stat.state != STATES.SCHED_CANCELLED:
                        # Sets status based on the result of sched.cancel_job. 
                        # Ran into trouble when 'cancelling' jobs that never 
                        # actually started, ie. build errors/created job states. 
                        test.status.set(sched.cancel_job(test).state,
                                     sched.cancel_job(test).note)
                        utils.fprint("test {} cancelled."
                                  .format(test_id), file=self.outfile,
                                     color=utils.GREEN)

                    else:
                        utils.fprint("test {} could not be cancelled, has state: {}."
                            .format(test_id, stat.state), file=self.outfile,
                                             color=utils.RED)

                except PavTestError as err:
                    utils.fprint("Test {} could not be cancelled, cannot be" \
                                 " found. \n{}".format(test_id, err), file=self.errfile,
                                 color=utils.RED)
                    continue

            # Gets updated list of tests that actually existed. 
            test_list = update_list

        # Only prints statuses of tests if option is selected
        # and test_list is not empty, therefore atleast 1 test
        # was a valid test
        if args.status and test_list:
            return print_from_test_obj(pav_cfg, test_list, self.outfile, args.json)

        return 0

