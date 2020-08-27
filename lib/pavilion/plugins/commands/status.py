"""The Status command, along with useful functions that make it easy for
other commands to print statuses."""

import errno
import os
import time
from datetime import datetime
from typing import List, Union

from pavilion import commands
from pavilion import dir_db
from pavilion import filters
from pavilion import system_variables
from pavilion import output
from pavilion import schedulers
from pavilion import series
from pavilion.series import TestSeries, TestSeriesError
from pavilion import test_run
from pavilion import utils
from pavilion.status_file import STATES
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


def get_last_ctime(path):
    """Gets the time path was modified."""
    mtime = os.path.getmtime(path)
    ctime = str(time.ctime(mtime))
    ctime = ctime[11:19]
    return ctime


def status_from_test_obj(pav_cfg: dict,
                         *test_objs: TestRun):
    """Takes a test object or list of test objects and creates the dictionary
    expected by the print_status function.

:param pav_cfg: Pavilion base configuration.
:param test_obj: Pavilion test object.
:return: List of dictionary objects containing the test ID, name,
         statt time of state update, and note associated with that state.
:rtype: list(dict)
    """

    test_statuses = []

    for test in test_objs:
        status_f = test.status.current()

        if status_f.state == STATES.SCHEDULED:
            sched = schedulers.get_plugin(test.scheduler)
            status_f = sched.job_status(pav_cfg, test)
        elif status_f.state == STATES.BUILDING:
            last_update = get_last_ctime(test.builder.log_updated())
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

    return test_statuses


def get_test_statuses(pav_cfg, test_ids):
    """Return the statuses for all tests, up to the limit in args.limit.
    :param List[int] test_ids: A list of test ids to load.
    """

    test_statuses = []

    for test_id in test_ids:
        try:
            test = TestRun.load(pav_cfg, test_id)
            test_statuses.append(status_from_test_obj(pav_cfg, test)[0])

        except (TestRunError, TestRunNotFoundError) as err:
            test_statuses.append({
                'test_id': test_id,
                'name':    "",
                'state':   STATES.UNKNOWN,
                'time':    None,
                'note':    "Test not found: {}".format(err)
            })

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
                'time':    None,
                'note':    "Error loading test: {}".format(err),
            })

    statuses = status_from_test_obj(pav_cfg, *test_obj_list)

    if statuses is not None:
        test_statuses = test_statuses + statuses
    return test_statuses


def print_status(statuses, outfile, json=False, show_skipped=False):
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

    if not show_skipped:
        statuses = [status for status in statuses
                    if status['state'] != STATES.SKIPPED]

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

    status_list = status_from_test_obj(pav_cfg, *test_obj)
    return print_status(status_list, outfile, json)


class StatusCommand(commands.Command):
    """Prints the status of a set of tests."""

    def __init__(self):
        super().__init__('status', 'Check the status of a test, list of tests,'
                                   ' or test series.',
                         short_help="Get status of tests.")

    def _setup_arguments(self, parser):

        pf_group = parser.add_mutually_exclusive_group()

        parser.add_argument(
            '-j', '--json', action='store_true', default=False,
            help='Give output as json, rather than as standard human readable.'
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help="The name(s) of the tests to check.  These may be any mix of "
                 "test IDs and series IDs. Use 'last' to get just the last "
                 "series you ran."
        )
        parser.add_argument(
            '-l', '--limit', type=int,
            help="Max number of tests to display."
        )
        parser.add_argument(
            '-s', '--summary', default=False, action='store_true',
            help='Display a single line summary of test statuses.'
        )
        parser.add_argument(
            '-k', '--show-skipped', default=False, action='store_true',
            help='Show the status of skipped tests.')

        parser.add_argument(
            '-u', '--user', type=str, default=utils.get_login(),
            help='Filter status by user. Defaults '
        )
        parser.add_argument(
            '-o', '--older', action='store_true',
            help='Orders status by oldest test first'
        )
        parser.add_argument(
            '-n', '--newer', action='store_true',
            help='Orders status by newest test first.'
        )
        pf_group.add_argument(
            '-p', '--passed', action='store_true',
            help='Filter status by tests passed.'
        )
        pf_group.add_argument(
            '-f', '--failed', action='store_true',
            help='Filter status by tests failed.'
        )
        parser.add_argument(
            '-c', '--complete', action='store_true',
            help='Filter status by tests completed.'
        )
        parser.add_argument(
            '-i', '--incomplete', action='store_true',
            help='Filter status by tests incomplete.'
        )
        parser.add_argument(
            '--sys_name', type=str,
            help='Filter status by type of machine.'
        )
        parser.add_argument(
            '--older_than', type=str,
            help='Filter tests older than x.'
        )
        parser.add_argument(
            '--newer_than', type=str, default='1 day',
            help='Filter tests newer than x.'
        )

    def run(self, pav_cfg, args):
        """Gathers and prints the statuses from the specified test runs and/or
        series."""

        if args.sys_name is None:
            args.sys_name = system_variables.get_vars(defer=True)['sys_name']

        older_than = None
        if args.older_than is not None:
            try:
                older_than = utils.retrieve_datetime(args.older_than)
            except ValueError as msg:
                output.fprint(
                    "Invalid older than date.\n{}".format(msg.args[0]),
                    color=output.RED, file=self.errfile)

        newer_than = None
        if args.newer_than is not None:
            try:
                newer_than = utils.retrieve_datetime(args.newer_than)
            except ValueError as msg:
                output.fprint(
                    "Invalid newer than date.\n{}".format(msg.args[0]),
                    color=output.RED, file=self.errfile)

        filter_func = filters.make_test_run_filter(
            complete=args.complete,
            incomplete=args.incomplete,
            passed=args.passed,
            failed=args.failed,
            users=[args.user],
            sys_names=[args.sys_name],
            older_than=older_than,
            newer_than=newer_than,
        )

        if args.tests:

            test_paths = []
            for test_id in args.tests:
                if test_id == 'last':
                    test_id = series.TestSeries.load_user_series_id(pav_cfg)

                if test_id.startswith('s'):
                    try:
                        test_paths.extend(
                            TestSeries.list_series_tests(pav_cfg, test_id))
                    except TestSeriesError:
                        output.fprint("Invalid series id '{}'".format(test_id))
                        return errno.EINVAL
                else:
                    try:
                        test_id = int(test_id)
                    except ValueError:
                        output.fprint("Invalid test id '{}'".format(test_id))

                    test_dir = dir_db.make_id_path(
                        pav_cfg.working_dir/'test_runs', test_id)

                    if not test_dir.exists():
                        output.fprint("No such test '{}'".format(test_id))
                        return errno.EINVAL

                    test_paths.append(test_dir)

        else:
            test_paths = dir_db.select(
                id_dir=pav_cfg.working_dir/'test_runs',
                filter_func=filter_func,
                limit=args.limit)

        test_ids = dir_db.paths_to_ids(test_paths)
        statuses = get_test_statuses(pav_cfg, test_ids)

        if args.summary:
            return self.print_summary(statuses)
        else:
            return print_status(statuses, self.outfile, args.json,
                                args.show_skipped)

    def display_history(self, pav_cfg, args):
        """Display_history takes a test_id from the command
        line arguments and formats the status file from the id
        and displays it for the user through draw tables.
        :param pav_cfg: The pavilion config.
        :param argparse namespace args: The test via command line
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
                        'time': datetime.strptime(val[0],
                                                  '%Y-%m-%dT%H:%M:%S.%f'),
                        'note': val[2]
                    })
        except (TestRunError, TestRunNotFoundError):
            output.fprint("The test_id {} does not exist in your "
                          "working directory.".format(args.history),
                          file=self.errfile,
                          color=output.RED)
            return errno.EINVAL

        fields = ['state', 'time', 'note']
        output.draw_table(
            outfile=self.outfile,
            field_info={
                'time': {'transform': output.get_relative_timestamp}
            },
            fields=fields,
            rows=states,
            title='Status history for test {} (id: {})'.format(name_final,
                                                               id_final))

        return ret_val

    def print_summary(self, statuses):
        """Print_summary takes in a list of test statuses.
        It summarizes basic state output and displays
        the data to the user through draw_table.
        :param statuses: state list of current jobs
        :rtype: int
        """
        # Populating table dynamically requires dict

        summary_dict = {}
        passes = 0
        ret_val = 0
        total_tests = len(statuses)
        rows = []
        fields = ['State', 'Amount', 'Percent']
        fails = 0

        # Shrink statues dict to singular keys with total
        # amount of key as the value
        for test in statuses:
            if test['state'] not in summary_dict.keys():
                summary_dict[test['state']] = 1
            else:
                summary_dict[test['state']] += 1

            # Gathers info on passed tests from completed tests.
            if 'COMPLETE' in test['state'] and 'PASS' in test['note']:
                passes += 1

        if 'COMPLETE' in summary_dict.keys():
            fails = summary_dict['COMPLETE'] - passes
            fields = ['State', 'Amount', 'Percent', 'PASSED', 'FAILED']

        for key, value in summary_dict.items():
            #  Build the rows for drawtables.

            #  Determine Color.
            if key.endswith('ERROR') or key.endswith('TIMEOUT') or \
               key.endswith('FAILED') or key == 'ABORTED' or key == 'INVALID':
                color = output.RED
            elif key == 'COMPLETE':
                color = output.GREEN
            elif key == 'SKIPPED':
                color = output.YELLOW
            elif key == 'RUNNING' or key == 'SCHEDULED' \
                    or key == 'PREPPING_RUN' \
                    or key == 'BUILDING' or key == 'BUILD_DONE' \
                    or key == 'BUILD_REUSED':
                color = output.CYAN
            else:
                color = output.WHITE  # Not enough to warrant color.

            # Populating rows...
            if key == 'COMPLETE':  # only time we need to populate pass/fail
                rows.append(
                    {'State': output.ANSIString(key, color),
                     'Amount': value,
                     'Percent': '{0:.0%}'.format(value / total_tests),
                     'PASSED': '{0:.0%}'.format(passes / value)
                               + ',({}/{})'.format(passes, value),
                     'FAILED': '{0:.0%}'.format(fails / value)
                               + ',({}/{})'.format(fails, value)}
                )
            else:
                rows.append(
                    {'State': output.ANSIString(key, color),
                     'Amount': value,
                     'Percent': '{0:.0%}'.format(value / total_tests)}
                )

        field_info = {
            'PASSED': {
                'transform': lambda t: output.ANSIString(t, output.GREEN)
            },
            'FAILED': {
                'transform': lambda t: output.ANSIString(t, output.RED),
            }}

        output.draw_table(outfile=self.outfile,
                          field_info=field_info,
                          fields=fields,
                          rows=rows,
                          border=True,
                          title='Test Summary')

        return ret_val
