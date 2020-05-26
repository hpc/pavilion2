"""The Status command, along with useful functions that make it easy for
other commands to print statuses."""

import errno
import os
import re
import time

from datetime import datetime
from pavilion import commands
from pavilion import output
from pavilion import schedulers
from pavilion import series
from pavilion import test_run
from pavilion.status_file import STATES
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


def get_last_ctime(path):
    """Gets the time path was modified."""
    mtime = os.path.getmtime(path)
    ctime = str(time.ctime(mtime))
    ctime = ctime[11:19]
    return ctime


def status_from_test_obj(pav_cfg, test_obj):
    """Takes a test object or list of test objects and creates the dictionary
    expected by the print_status function.

:param dict pav_cfg: Pavilion base configuration.
:param Union[TestRun,[TestRun] test_obj: Pavilion test object.
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
            sched = schedulers.get_plugin(test.scheduler)
            status_f = sched.job_status(pav_cfg, test)
        elif status_f.state == STATES.BUILDING:
            last_update = get_last_ctime(test.path/'build.log')
            status_f.note = ' '.join([status_f.note,
                                      'Last updated: ',
                                      last_update])
        elif status_f.state == STATES.RUNNING:
            last_update = get_last_ctime(test.path/'run.log')
            status_f.note = ' '.join([status_f.note,
                                      'Last updated:',
                                      last_update])

        test_statuses.append({
            'test_id': test.id,
            'name':    test.name,
            'state':   status_f.state,
            'time':    status_f.when,
            'note':    status_f.note,
        })

    test_statuses.sort(key=lambda x: x['test_id'])
    return test_statuses


def get_all_tests(pav_cfg, args):
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
                'name':    "",
                'state':   STATES.UNKNOWN,
                'time':    "",
                'note':    "Test not found: {}".format(err)
            })

    statuses = status_from_test_obj(pav_cfg, test_obj_list)

    if statuses is not None:
        test_statuses = test_statuses + statuses

    return test_statuses


def get_tests(pav_cfg, args, errfile):
    """
    Gets the tests depending on arguments.

:param pav_cfg: The pavilion config
:param argparse namespace args: The tests via command line args.
:param errfile: stream to output errors as needed
:return: List of test objects
    """

    if not args.tests:
        # Get the last series ran by this user
        series_id = series.TestSeries.load_user_series_id(pav_cfg)
        if series_id is not None:
            args.tests.append(series_id)
        else:
            raise commands.CommandError(
                "No tests specified and no last series was found."
            )

    test_list = []

    for test_id in args.tests:
        # Series
        if test_id.startswith('s'):
            try:
                test_list.extend(series.TestSeries.from_id(pav_cfg,
                                                           test_id).tests)
            except series.TestSeriesError as err:
                output.fprint(
                    "Suite {} could not be found.\n{}"
                    .format(test_id, err),
                    file=errfile,
                    color=output.RED
                )
                continue
        # Test
        else:
            test_list.append(test_id)
    test_list = list(map(int, test_list))
    return test_list


def get_statuses(pav_cfg, args, errfile):
    """Get the statuses of the listed tests or series.

:param pav_cfg: The pavilion config.
:param argparse namespace args: The tests via the command line args.
:param errfile: stream to output errors as needed.
:returns: List of dictionary objects with the test id, name, state,
          time that the most recent status was set, and the associated
          note.
"""

    test_list = get_tests(pav_cfg, args, errfile)
    test_statuses = []
    test_obj_list = []
    for test_id in test_list:
        try:
            test = TestRun.load(pav_cfg, test_id)
            test_obj_list.append(test)
        except (TestRunError, TestRunNotFoundError) as err:
            test_statuses.append({
                'test_id': test_id,
                'name':    "",
                'state':   STATES.UNKNOWN,
                'time':    "",
                'note':    "Error loading test: {}".format(err),
            })

    statuses = status_from_test_obj(pav_cfg, test_obj_list)

    if statuses is not None:
        test_statuses = test_statuses + statuses
    return test_statuses


def display_history(pav_cfg, args, outfile):
    """Display_history takes a test_id from the command
    line arguments and formats the status file from the id
    and displays it for the user through draw tables.
    :param pav_cfg: The pavilion config.
    :param argparse namespace args: The test via command line
    :param stream outfile: Stream to which states are printed
    :rtype int"""

    ret_val = 0
    # status_path locates the status file per test_run id.
    status_path = (pav_cfg.working_dir / 'test_runs' /
                   str(args.history).zfill(7) / 'status')

    try:
        test = TestRun.load(pav_cfg, args.history)
        name_final = test.name
        id_final = test.id
        states = []  # dictionary list for table output

        with status_path.open() as file:
            for line in file:
                val = line.split(' ', 2)
                states.append({
                    'state': val[1],
                    'time': datetime.strptime(val[0], '%Y-%m-%dT%H:%M:%S.%f'),
                    'note': val[2]
                })
    except (TestRunError, TestRunNotFoundError) as err:
        output.fprint("The test_id {} does not exist in your "
                      "working directory.".format(args.history),
                      color=output.RED)
        return errno.EINVAL

    fields = ['state', 'time', 'note']
    output.draw_table(
        outfile=outfile,
        field_info={
            'time': {'transform': output.get_relative_timestamp}
        },
        fields=fields,
        rows=states,
        title='Status history for test {} (id: {})'.format(name_final,
                                                           id_final))

    return ret_val


def print_summary(statuses, outfile):
    """Print_summary takes in a list of test statuses.
    It summarizes basic state output and displays
    the data to the user through draw_table.
    :param statuses: state list of current jobs
    :param outfile:
    :rtype: int
    """

    total_tests = len(statuses)
    one_success = False
    total_pass = 0
    total_fail = 0
    total_skipped = 0
    state_completed = 0
    state_running = 0
    state_error = 0
    ret_val = 0

    for test in statuses:  # collect statistical info on job list.
        # For a summary table we will generalize some output.
        if 'COMPLETE' in test['state']:
            one_success = True
            state_completed += 1
            if 'PASS' in test['note']:
                total_pass += 1
            else:
                total_fail += 1

        elif 'SKIPPED' in test['state']:
            total_skipped += 1

        elif 'RUNNING' in test['state'] or \
             'SCHEDULED' in test['state'] or \
             'PREPPING_RUN' in test['state']:
            state_running += 1

        else:
            # We assume a fail with running/complete/skip not found.
            # Also tests not found will be logged here.
            state_error += 1

    if not one_success:  # Catch divide be zero error.
        total_pass = 0
        total_fail = 0
    else:
        total_pass = total_pass/state_completed
        total_fail = total_fail/state_completed

    fields = ['State', 'Amount', 'Percent', 'PASSED', 'FAILED']
    try:
        rows = [
            {'State': output.ANSIString('COMPLETED', output.COLORS.get(
                'GREEN')),
             'Amount': state_completed,
             'Percent': '{0:.0%}'.format(state_completed/total_tests),

             'PASSED': '{0:.0%}'.format(total_pass),
             'FAILED': '{0:.0%}'.format(total_fail)},

            {'State': output.ANSIString('RUNNING/SCHEDULED', output.COLORS.get(
                'CYAN')),
             'Amount': state_running,
             'Percent': '{0:.0%}'.format(state_running / total_tests)},

            {'State': output.ANSIString('RUN/BUILD_FAILED', output.COLORS.get(
                'RED')),
             'Amount': state_error,
             'Percent': '{0:.0%}'.format(state_error / total_tests)},

            {'State': output.ANSIString('SKIPPED', output.COLORS.get('YELLOW')),
             'Amount': total_skipped,
             'Percent': '{0:.0%}'.format(total_skipped/total_tests)}]

    except ArithmeticError:
        output.fprint("No tests found in the working dir.", color=output.RED)
        return errno.EINVAL

    field_info = {
        'PASSED': {
            'transform': lambda t: output.ANSIString(t, output.COLORS.get(
                'GREEN')),
        },
        'FAILED': {
            'transform': lambda t: output.ANSIString(t, output.COLORS.get(
                'RED')),
        }
    }

    output.draw_table(outfile=outfile,
                      field_info=field_info,
                      fields=fields,
                      rows=rows,
                      border=True,
                      title='Test Summary'
                      )
    return ret_val


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
        output.json_dump(json_data, outfile)
    else:
        fields = ['test_id', 'name', 'state', 'time', 'note']
        output.draw_table(
            outfile=outfile,
            field_info={
                'time': {'transform': output.get_relative_timestamp}
            },
            fields=fields,
            rows=statuses,
            title='Test statuses')

    return ret_val


def print_from_test_obj(pav_cfg, test_obj, outfile, json=False):
    """Print the statuses given a list of test objects or a single test object.

    :param dict pav_cfg: Base pavilion configuration.
    :param Union(test_run.TestRun,list(test_run.TestRun) test_obj:
        Single or list of test objects.
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
                                   ' or test series.',
                         short_help="Get status of tests.")

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
        parser.add_argument(
            '--history', type=int,
            help="Shows the full status history of a job."
        )
        parser.add_argument(
            '-s', '--summary', default=False, action='store_true',
            help='Summary will display a fantastic table full of bright colors '
                 'and useful information. '
        )


    def run(self, pav_cfg, args):
        """Gathers and prints the statuses from the specified test runs and/or
        series."""
        try:
            if not args.all:
                test_statuses = get_statuses(pav_cfg, args, self.errfile)
            else:
                test_statuses = get_all_tests(pav_cfg, args)
        except commands.CommandError as err:
            output.fprint("Status Error:", err, color=output.RED)
            return 1
        
        if args.summary:
            return print_summary(test_statuses, self.outfile)
        elif args.history:
            return display_history(pav_cfg, args, self.outfile)
        else:
            return print_status(test_statuses, self.outfile, args.json)
