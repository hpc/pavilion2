from pavilion import commands
from pavilion import pavtest
from pavilion import status_file
from pavilion import utils
from pavilion.suite import Suite
import sys

class StatusCommand(commands.Command):

    def __init__(self):
        super().__init__('status', 'Check the status of a test, list of tests,'
                         'or test suite.', short_help="Get status of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to check.  These may be any mix of'
                 'test IDs and suite IDs.  If no value is provided, the most'
                 'recent test or suite submitted by this user is checked.'
        )

    def run(self, pav_config, args):

        test_list = []
        test_statuses = []

        if not args.tests:
            pav_suite = Suite.from_id(pav_config, Suite.load_suite_id)
            test_list = pav_suite.tests
        else:
            for test_id in args.tests:
                if test_id.startswith('s'):
                    test_list.extend(Suite.from_id(pav_config,
                                                   test_id[1:]).tests
                                    )
                else:
                    test_list.append(test_id)

        for test_id in test_list:
            status_file = None
            pav_test = pavtest.PavTest.from_id(pav_config, test_id)
            status_file = status_file.StatusFile(pav_test.status).current()

            test_statuses.append({
                'test_id': test_id,
                'state': status_file.state,
                'time': status_file.when,
                'note': status_file.note,
            })

        if args.json:
            json_data = {'statuses': test_statuses}
            utils.output_json(sys.stdout, json_data)
        else:
            cols = ['test_id', 'state', 'time', 'note']
            utils.draw_table(sys.stdout, {}, cols, test_statuses,
                             title='Test statuses')
