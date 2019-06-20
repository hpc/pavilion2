from pavilion import commands
from pavilion import schedulers
from pavilion.status_file import STATES
from pavilion import utils
from pavilion import series
from pavilion.pav_test import PavTest, PavTestError, PavTestNotFoundError
import errno
import sys


class StatusCommand(commands.Command):

    def __init__(self):
        super().__init__('status', 'Check the status of a test, list of tests,'
                         ' or test series.', short_help="Get status of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to check.  These may be any mix of '
                 'test IDs and series IDs.  If no value is provided, the most '
                 'recent series submitted by this user is checked.'
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
                    test_list.extend(
                        series.TestSeries.from_id(
                            pav_cfg,
                            int(test_id[1:])).tests)
                except series.TestSeriesError as err:
                    utils.fprint(
                        "Suite {} could not be found.\n{}"
                        .format(test_id[1:], err),
                        file=self.errfile,
                        color=utils.RED
                    )
                    continue
            else:
                test_list.append(test_id)

        test_list = map(int, test_list)

        test_statuses = []
        for test_id in test_list:
            try:
                test = PavTest.load(pav_cfg, test_id)
            except (PavTestError, PavTestNotFoundError) as err:
                test_statuses.append({
                    'test_id': test_id,
                    'name': "",
                    'state': STATES.UNKNOWN,
                    'time': "",
                    'note': "Test not found.",
                })
                continue

            status_f = test.status.current()

            if status_f.state == STATES.SCHEDULED:
                sched = schedulers.get_scheduler_plugin(test.scheduler)
                status_f = sched.job_status(pav_cfg, test)

            test_statuses.append({
                'test_id': test_id,
                'name': test.name,
                'state': status_f.state,
                'time': status_f.when.strftime("%d %b %Y %H:%M:%S %Z"),
                'note': status_f.note,
            })

        if args.json:
            json_data = {'statuses': test_statuses}
            utils.json_dump(json_data, self.outfile)
        else:
            fields = ['test_id', 'name', 'state', 'time', 'note']
            utils.draw_table(
                outfile=self.outfile,
                field_info={},
                fields=fields,
                rows=test_statuses,
                title='Test statuses')

        return 0

    def _get_tests(self, pav_cfg, tests):
        """Get the list of tests given those specified in the arguments.
        :param pav_cfg: The pavilion config.
        :param list(str) tests: The tests via the command line args.
        :returns: Test ids.
        """

    def __repr__(self):
        return str(self)
