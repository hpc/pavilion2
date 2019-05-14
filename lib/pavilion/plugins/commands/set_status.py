from pavilion import commands
from pavilion import pavtest
from pavilion import status_file
from pavilion import utils
from pavilion import suite
import sys

class SetStatusCommand(commands.Command):

    def __init__(self):
        super().__init__('set_status', 'Set the status of a test, list of '
                         'tests, or test suite.',
                         short_help="Set status of tests.")

    def _setup_arguments(self, parser):

        parser.add_argument(
            '-s', '--state', action='store', default='RUN_USER',
            help='State to set for the test, tests, or suite of tests.'
        )
        parser.add_argument(
            '-n', '--note', action='store', default=None,
            help='Note to set for the test, tests, or suite of tests.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name(s) of the tests to set.  These may be any mix of '
                 'test IDs and suite IDs.  If no value is provided, the most '
                 'recent suite submitted by this user is used.'
        )

    def run(self, pav_config, args):

        test_list = []
        test_statuses = []

        if not args.tests:
            try:
                pav_suite = suite.Suite.from_id(pav_config,
                    int(suite.Suite.load_suite_id()))
            except suite.SuiteError as err:
                print("No test was specified and last suite run by this"
                      " user cannot be found.\n{}".format(err))
                return 1
            test_list = pav_suite.tests
        else:
            for test_id in args.tests:
                if test_id.startswith('s'):
                    try:
                        test_list.extend(suite.Suite.from_id(pav_config,
                            int(test_id[1:])).tests)
                    except suite.SuiteError as err:
                        print("Suite {} could not be found.\n{}".format(
                            test_id[1:], err))
                        return 1
                else:
                    test_list.append(test_id)

        for test_id in test_list:
            pav_test = None
            status_f = None
            try:
                pav_test = pavtest.PavTest.load(pav_config, int(test_id))
            except pavtest.PavTestError or pavtest.PavTestNotFoundError as err:
                print("Test {} could not be opened.\n{}".format(test_id, err))

            if pav_test is not None:
                status_f = status_file.StatusFile(pav_test.status.path)

            if status_f is not None:
                status_f.set(args.state, args.note)

        return 0

    def __repr__(self):
        return str(self)
