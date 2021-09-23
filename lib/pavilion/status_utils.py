"""A collection of utilities for getting the current status of test runs
and series."""

from concurrent.futures import ThreadPoolExecutor
import os
import sys
import time
from functools import partial
from typing import TextIO, List

from pavilion import config
from pavilion import exceptions
from pavilion import output
from pavilion import schedulers
from pavilion import series
from pavilion.status_file import STATES
from pavilion.test_run import (TestRun)
from pavilion.exceptions import TestRunError, TestRunNotFoundError


def get_last_ctime(path):
    """Gets the time path was modified."""
    mtime = os.path.getmtime(str(path))
    ctime = str(time.ctime(mtime))
    ctime = ctime[11:19]
    return ctime


def status_from_test_obj(pav_cfg: dict, test: TestRun):

    """Takes a test object or list of test objects and creates the dictionary
    expected by the print_status function.

:param pav_cfg: Pavilion base configuration.
:param test: Pavilion test object.
:return: List of dictionary objects containing the test ID, name,
         stat time of state update, and note associated with that state.
:rtype: list(dict)
    """

    status_f = test.status.current()

    if status_f.state == STATES.SCHEDULED:
        sched = schedulers.get_plugin(test.scheduler)
        status_f = sched.job_status(pav_cfg, test)
    elif status_f.state == STATES.BUILDING:
        last_update = test.builder.log_updated()
        status_f.note = ' '.join([
            status_f.note, '\nLast updated: ',
            str(last_update) if last_update is not None else '<unknown>'])
    elif status_f.state == STATES.RUNNING:
        last_update = get_last_ctime(test.path/'run.log')
        status_f.note = ' '.join([
            status_f.note, '\nLast updated:',
            str(last_update) if last_update is not None else '<unknown>'])

    return {
        'test_id': test.id,
        'name':    test.name,
        'state':   status_f.state,
        'time':    status_f.when,
        'note':    status_f.note,
    }


def get_tests(pav_cfg, tests: List['str'], errfile: TextIO) -> List[int]:
    """Convert a list of test id's and series id's into a list of test id's.

    :param pav_cfg: The pavilion config
    :param tests: A list of tests or test series names.
    :param errfile: stream to output errors as needed
    :return: List of test objects
    """

    tests = [str(test) for test in tests.copy()]

    if not tests:
        # Get the last series ran by this user
        series_id = series.load_user_series_id(pav_cfg)
        if series_id is not None:
            tests.append(series_id)
        else:
            raise exceptions.CommandError(
                "No tests specified and no last series was found."
            )

    test_list = []

    for test_id in tests:
        # Series start with 's', like 'snake'.
        if test_id.startswith('s'):
            try:
                test_list.extend(series.TestSeries.load(pav_cfg, test_id).tests)
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

    return list(map(int, test_list))


def get_status(test: TestRun, pav_conf):
    """Return the status of a single test_id.
    Allows the statuses to be queried in parallel with map.
    :param test: The test id being queried.
    :param pav_conf: The Pavilion config.
    """

    try:
        test_status = status_from_test_obj(pav_conf, test)
    except (TestRunError, TestRunNotFoundError) as err:
        test_status = {
            'test_id': test.full_id,
            'name':    test.name,
            'state':   STATES.UNKNOWN,
            'time':    None,
            'note':    "Test not found: {}".format(err)
        }

    return test_status


def get_statuses(pav_cfg, tests: List[TestRun]):
    """Return the statuses for all given test id's.
    :param pav_cfg: The Pavilion config.
    :param tests: A list of test ids to load.
    """

    get_this_status = partial(get_status, pav_conf=pav_cfg)

    with ThreadPoolExecutor(pav_cfg['max_threads']) as pool:
        return list(pool.map(get_this_status, tests))


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


def print_from_tests(pav_cfg, tests, outfile, json=False):
    """Print the statuses given a list of test objects or a single test object.

    :param dict pav_cfg: Base pavilion configuration.
    :param Union(test_run.TestRun,list(test_run.TestRun) tests:
        Single or list of test objects.
    :param bool json: Whether the output should be a JSON object or not.
    :param stream outfile: Stream to which the statuses should be printed.
    :return: 0 for success.
    :rtype: int
    """

    status_list = [status_from_test_obj(pav_cfg, test) for test in tests]
    return print_status(status_list, outfile, json)


def status_history_from_test_obj(test: TestRun) -> List[dict]:
    """Takes a test object and creates the dictionary expected by the
    print_status_history function

    :param test: Pavilion test run object.
    :return: List of dictionary objects containing the test ID, name,
             stat time of state update, and note associated with that state.
    """

    status_history = []

    status_history_list = test.status.history()

    for status in status_history_list:
        status_history.append({
            'state':   status.state,
            'time':    status.when,
            'note':    status.note,
        })

    return status_history


def print_status_history(pav_cfg: dict, test: TestRun, outfile: TextIO,
                         json: bool = False):
    """Print the status history for a given test object.

    :param pav_cfg: Base pavilion configuration.
    :param test: Single test object.
    :param outfile: Stream to which the status history should be printed.
    :param json: Whether the output should be a JSON object or not
    :return: 0 for success.
    """

    status_history = status_history_from_test_obj(test)

    ret_val = 1
    for status in status_history:
        if status['note'] != "Test not found.":
            ret_val = 0
    if json:
        json_data = {'status_history': status_history}
        output.json_dump(json_data, outfile)
    else:
        fields = ['state', 'time', 'note']
        output.draw_table(
            outfile=outfile,
            field_info={
                'time': {'transform': output.get_relative_timestamp}
            },
            fields=fields,
            rows=status_history,
            title='Test {} Status History ({})'.format(test.id, test.name))

    return ret_val
