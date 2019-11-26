import sys

from pavilion import commands
from pavilion import schedulers
from pavilion import series
from pavilion import utils
from pavilion import test_run
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError
from pavilion.status_file import STATES


def status_from_test_obj(pav_cfg, test_obj):
    """Takes a test object or list of test objects and creates the dictionary
    expected by the print_status function.

:param dict pav_cfg: Pavilion base configuration.
:param test_run.TestRun test_obj: Pavilion test object.
:return: List of dictionary objects containing the test ID, name,
         statt time of state update, and note associated with that state.
:rtype: list(dict)
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
            'time': status_f.when,
            'note': status_f.note,
        })

    test_statuses.sort(key=lambda x: x['test_id'])
    return test_statuses


def get_all_tests(pav_cfg, args, errfile):
    """Return the statuses for all tests, up to the limit in args.limit."""

    latest_tests = test_run.get_latest_tests(pav_cfg, args.limit)

    test_obj_list = []
    test_statuses = []
    for test_id in latest_tests:
        try:
            test = TestRun.load(pav_cfg, test_id)
            test_obj_list.append(test)
        except (TestRunError, TestRunNotFoundError) as err:
            test_statuses.append({
                'test_id': test_id,
                'name': "",
                'state': STATES.UNKNOWN,
                'time': "",
                'note': "Test not found."
            })

    statuses = status_from_test_obj(pav_cfg, test_obj_list)

    if statuses is not None:
        test_statuses = test_statuses + statuses

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

    # if (not args.tests) and (not args.all):
    if not args.tests:
        # Get the last series ran by this user.
        series_id = series.TestSeries.load_user_series_id(pav_cfg)
        if series_id is not None:
            args.tests.append(series_id)
        else:
            raise commands.CommandError(
                "No tests specified and no last series was found.")

    test_list = []

    for test_id in args.tests:
        # Series
        if test_id.startswith('s'):
            try:
                test_list.extend(
                    series.TestSeries.from_id(pav_cfg, test_id).tests)
            except series.TestSeriesError as err:
                utils.fprint(
                    "Suite {} could not be found.\n{}"
                    .format(test_id, err),
                    file=errfile,
                    color=utils.RED
                )
                continue
        # Test
        else:
            test_list.append(test_id)

    test_list = list(map(int, test_list))

    test_statuses = []
    test_obj_list = []
    for test_id in test_list:
        try:
            test = TestRun.load(pav_cfg, test_id)
            test_obj_list.append(test)
        except (TestRunError, TestRunNotFoundError) as err:
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
:return: success or failure.
:rtype: int
"""

    ret_val = 1
    for stat in statuses:
        if stat['note'] != "Test not found.":
            ret_val = 0

    if json:
        json_data = {'statuses': statuses}
        utils.json_dump(json_data, outfile)
    else:
        fields = ['test_id', 'name', 'state', 'time', 'note']
        utils.draw_table(
            outfile=outfile,
            field_info={
                'time': {'transform': utils.get_relative_timestamp}
            },
            fields=fields,
            rows=statuses,
            title='Test statuses')

    return ret_val


def print_from_test_obj(pav_cfg, test_obj, outfile, json=False):
    """Print the statuses given a list of test objects or a single test object.

:param dict pav_cfg: Base pavilion configuration.
:param test_run.TestRun test_obj: Single or list of test objects.
:param bool json: Whether the output should be a JSON object or not.
:param stream outfile: Stream to which the statuses should be printed.
:return: 0 for success.
:rtype: int
"""
    status_list = status_from_test_obj(pav_cfg, test_obj)
    return print_status(status_list, outfile, json)


class StatusCommand(commands.Command):
    """Prints the status of a set of tests."""

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
            '-l', '--limit', type=int, default=10,
            help='Max number of tests displayed if --all is used.'
        )

    def run(self, pav_cfg, args):
        try:
            if not args.all:
                test_statuses = get_statuses(pav_cfg, args, self.errfile)
            else:
                test_statuses = get_all_tests(pav_cfg, args, self.errfile)
        except commands.CommandError as err:
            utils.fprint("Status Error:", err, color=utils.RED)
            return 1

        return print_status(test_statuses, self.outfile, args.json)

    def __repr__(self):
        return str(self)
