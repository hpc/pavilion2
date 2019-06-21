from pavilion import commands
from pavilion import schedulers
from pavilion.status_file import STATES
from pavilion import utils
from pavilion import series
from pavilion.pav_test import PavTest, PavTestError, PavTestNotFoundError
import errno
import sys

def status_from_test_obj(pav_cfg, test_obj):
    """Takes a test object or list of test objects and creates the dictionary
    expected by the print_status function.
    :param dict pav_cfg: Pavilion base configuration.
    :param pav_test.PavTest test_obj: Pavilion test object.
    :return list List of dictionary objects containing the test ID, name, state,
                 time of state update, and note associated with that state.
    """
    if not isinstance(test_obj, list):
        test_obj = [test_obj]

    test_statuses = []

    for test in test_obj:
        status_f = test.status.current()

        if status_f.state == STATES.SCHEDULED:
            sched = schedulers.get_scheduler_plugin(test.scheduler)
            status_f = sched.job_status(pav_cfg, test)

        test_statuses.append({
            'test_id': test.id,
            'name': test.name,
            'state': status_f.state,
            'time': status_f.when.strftime("%d %b %Y %H:%M:%S %Z"),
            'note': status_f.note,
        })

    #return test_statuses.sort(key=lambda x: x['test_id'], reverse=True)
    return test_statuses

def get_statuses(pav_cfg, args, errfile):
    """Get the statuses of the listed tests or series.
    :param pav_cfg: The pavilion config.
    :param argparse namespace args: The tests via the command line args.
    :param errfile: stream to output errors as needed.
    :returns: List of dictionary objects with the test id, name, state,
              time that the most recent status was set, and the associated
              note.
    """

    if (not args.tests) and (not args.all):
        # Get the last series ran by this user.
        series_id = series.TestSeries.load_user_series_id()
        if series_id is not None:
            args.tests.append('s{}'.format(series_id))
            print("series id: " + str(series_id))
    
    if (not args.tests) and (not args.all):
        raise commands.CommandError("No tests found.")
   

    test_list = []

    # user wants all tests
    if args.all:
        if args.limit:
            limit = args.limit
        else:
            limit = 10
        print("max # of tests displayed: " + str(limit))
        # Get latest test
        last_series = series.TestSeries.load_user_series_id()
        last_tests = series.TestSeries.from_id(pav_cfg, last_series).tests
        last_test = max(last_tests, key=int)
        while limit is not 0:
            test_list.append(last_test)
            last_test = last_test - 1
            limit = limit - 1

    for test_id in args.tests:
        # Series 
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
                    file=errfile,
                    color=utils.RED
                )
                continue
        # Test
        else:
            test_list.append(test_id)

    #test_list = test_list.sort(reverse = True)
    #print(test_list)
    test_list = map(int, test_list)

    test_statuses = []
    test_obj_list = []
    for test_id in test_list:
        try:
            test = PavTest.load(pav_cfg, test_id)
            test_obj_list.append(test)
        except (PavTestError, PavTestNotFoundError) as err:
            test_statuses.append({
                'test_id': test_id,
                'name': "",
                'state': STATES.UNKNOWN,
                'time': "",
                'note': "Test not found.",
            })


    statuses = status_from_test_obj(pav_cfg, test_obj_list)

    if statuses is not None:
        test_statuses = test_statuses + statuses
    return test_statuses

def print_status(statuses, outfile, json=False):
    """Prints the statuses provided in the statuses parameter.
    :param list statuses: list of dictionary objects containing the test
                          ID, name, state, time of state update, and note
                          associated with that state.
    :param bool json: Whether state should be printed as a JSON object or
                      not.
    :param stream outfile: Stream to which the statuses should be printed.
    :return int success or failure.
    """
    if json:
        json_data = {'statuses': statuses}
        utils.json_dump(json_data, outfile)
    else:
        fields = ['test_id', 'name', 'state', 'time', 'note']
        utils.draw_table(
            outfile=outfile,
            field_info={},
            fields=fields,
            rows=statuses,
            title='Test statuses')

    return 0

def print_from_test_obj(pav_cfg, test_obj, outfile, json=False):
    """Print the statuses given a list of test objects or a single test object.
    :param dict pav_cfg: Base pavilion configuration.
    :param pav_test.PavTest test_obj: Single or list of test objects.
    :param bool json: Whether the output should be a JSON object or not.
    :param stream outfile: Stream to which the statuses should be printed.
    :return int 0 for success.
    """
    status_list = status_from_test_obj(pav_cfg, test_obj)
    return print_status(status_list, outfile, json)


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
        parser.add_argument(
            '-a', '--all', action='store_true',
            help='Displays all tests within a certain limit.'
        )
        parser.add_argument(
            '-l', '--limit', type=int,
            help='If -a/--all is used, then --limit is the number of last SUITES.'
        )

    def run(self, pav_cfg, args):

        test_statuses = get_statuses(pav_cfg, args, self.errfile)

        return print_status(test_statuses, self.outfile, args.json)

    def __repr__(self):
        return str(self)
