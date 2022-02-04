"""A collection of utilities for getting the current status of test runs
and series."""

import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TextIO, List

from pavilion import exceptions
from pavilion import output
from pavilion import schedulers
from pavilion import series
from pavilion.exceptions import TestRunError, TestRunNotFoundError, DeferredError
from pavilion.status_file import STATES
from pavilion.test_run import (TestRun)


def format_mtime(mtime):
    """Gets the time path was modified."""
    ctime = str(time.ctime(mtime))
    ctime = ctime[11:19]
    return ctime


RUNNING_UPDATE_TIMEOUT = 5


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

    if status_f.state in STATES.RUNNING:
        sched = schedulers.get_plugin(test.scheduler)
        status_f = sched.job_status(pav_cfg, test)
    elif status_f.state == STATES.BUILDING:
        last_update = test.builder.log_updated()
        status_f.note = ' '.join([
            status_f.note, '\nLast updated: ',
            str(last_update) if last_update is not None else '<unknown>'])
    elif status_f.state == STATES.RUNNING:
        log_path = test.path/'run.log'
        if log_path.exists():
            mtime = log_path.stat().st_mtime
        else:
            mtime = None

        if mtime is None or time.time() - mtime > RUNNING_UPDATE_TIMEOUT:
            sched = schedulers.get_plugin(test.scheduler)
            status_f = sched.job_status(pav_cfg, test)
        else:
            last_update = format_mtime(mtime)
            status_f.note = ' '.join([
                status_f.note, '\nLast updated:', last_update])

    try:
        nodes = test.var_man.get('sched.test_nodes', '')
    except DeferredError:
        nodes = ''

    result = test.results.get('result', '') or ''
    series = test.series or ''

    return {
        'job_id':  str(test.job) if test.job is not None else '',
        'name':    test.name,
        'nodes':   nodes,
        'note':    status_f.note,
        'result':  result,
        'series':  series,
        'state':   status_f.state,
        'test_id': test.id,
        'time':    status_f.when,
    }


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
            'job_id':  str(test.job) if test.job is not None else '',
            'name':    test.name,
            'nodes':   '',
            'note':    "Error getting test status: {}".format(err),
            'result':  '',
            'series':  '',
            'state':   STATES.UNKNOWN,
            'test_id': test.full_id,
            'time':    '',
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


def print_status(statuses, outfile, note=False, series=False, json=False):
    """Prints the statuses provided in the statuses parameter.

:param list statuses: list of dictionary objects containing the test_id,
                      job_id, name, state, time of state update, and note
                      associated with that state.
:param bool json: Whether state should be printed as a JSON object or
                  not.
:param stream outfile: Stream to which the statuses should be printed.
:return: success or failure.
:rtype: int
"""

    statuses.sort(key=lambda v: v.get('test_id'))

    if json:
        json_data = {'statuses': statuses}
        output.json_dump(json_data, outfile)
    else:
        fields = ['test_id', 'job_id', 'name', 'nodes', 'state', 'result', 'time']
        if series:
            fields.insert(0, 'series')
        if note:
            fields.append('note')
        output.draw_table(
            outfile=outfile,
            field_info={
                'time': {'transform': output.get_relative_timestamp},
                'test_id': {'title': 'Test'},
            },
            fields=fields,
            rows=statuses,
            title='Test statuses')

    return 0


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


def print_status_history(test: TestRun, outfile: TextIO, json: bool = False):
    """Print the status history for a given test object.

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
