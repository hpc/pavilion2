"""A collection of utilities for getting the current status of test runs
and series."""

import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TextIO, List

from pavilion import output
from pavilion import schedulers
from pavilion import utils
from pavilion.errors import TestRunError, TestRunNotFoundError, DeferredError
from pavilion.status_file import STATES
from pavilion.test_run import (TestRun)


def format_mtime(mtime):
    """Gets the time path was modified."""
    ctime = str(time.ctime(mtime))
    ctime = ctime[11:19]
    return ctime


RUNNING_UPDATE_TIMEOUT = 5


def status_from_test_obj(pav_cfg: dict, test: TestRun):

    """Takes a test object and creates the dictionary expected by the
    print_status function.

:param pav_cfg: Pavilion base configuration.
:param test: Pavilion test object.
:return: List of dictionary objects containing the test ID, name,
         stat time of state update, and note associated with that state.
:rtype: list(dict)
    """

    status_f = test.status.current()

    if status_f.state == STATES.BUILDING:
        # When building, the update time comes from the build log
        last_update = test.builder.log_updated()
        status_f.note = ' '.join([
            status_f.note, '\nLast updated: ',
            str(last_update) if last_update is not None else '<unknown>'])
    elif status_f.state in STATES.RUNNING:
        # When running check for recent run log updates, and check the
        # scheduler if things have gone on too long.

        log_path = test.path/'run.log'
        if log_path.exists():
            mtime = log_path.stat().st_mtime
        else:
            mtime = None

        if mtime is None or time.time() - mtime > RUNNING_UPDATE_TIMEOUT:
            sched = schedulers.get_plugin(test.scheduler)
            sched_status_f = sched.job_status(pav_cfg, test)
            if sched_status_f.state != STATES.SCHED_STARTUP:
                status_f = sched_status_f
        else:
            last_update = format_mtime(mtime)
            status_f.note = ' '.join([
                status_f.note, '\nLast updated:', last_update])

    elif status_f.state in STATES.SCHEDULED:
        # When the state is scheduled, get the real status from the scheduler.
        sched = schedulers.get_plugin(test.scheduler)
        status_f = sched.job_status(pav_cfg, test)

    try:
        # Use the actual node count one the test is running.
        nodes = test.var_man.get('sched.test_nodes', '')
    except DeferredError:
        # Otherwise use the chunk size when requesting all nodes
        # or the requested size otherwise.
        nodes = '({})'.format(test.var_man.get('sched.requested_nodes', '?'))

    result = test.results.get('result', '') or ''
    series_id = test.series or ''

    return {
        'job_id':  str(test.job) if test.job is not None else '',
        'name':    test.name,
        'nodes':   nodes,
        'note':    status_f.note,
        'part':    test.var_man.get('sched.partition'),
        'result':  result,
        'series':  series_id,
        'state':   status_f.state,
        'test_id': test.id if test.full_id.startswith('main') else test.full_id,
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
            'part':    '',
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


def print_status(statuses: List[dict], outfile,
                 note=False, series=False, json=False, sorter=False):
    """Prints the statuses provided in the statuses parameter.

:param statuses: list of dictionary objects containing the test_id,
                      job_id, name, state, time of state update, and note
                      associated with that state.
:param json: Whether state should be printed as a JSON object or
                  not.
:param note: Print the status note.
:param series: Print the series id.
:param sorter: Sort tests by sorter key.
:param stream outfile: Stream to which the statuses should be printed.
:return: success or failure.
:rtype: int
"""

    if json:
        json_data = {'statuses': statuses}
        output.json_dump(json_data, outfile)
    else:
        fields = ['test_id', 'job_id', 'name', 'nodes', 'part', 'state', 'result', 'time']
        if series:
            fields.insert(0, 'series')
        if note:
            fields.append('note')

        if sorter:
            flat_status = [utils.flatten_dictionary(status) for status in statuses]
            flat_sorted_statuses = utils.sort_table(sorter, flat_status)
        else:
            flat_sorted_statuses = statuses

        output.draw_table(
            outfile=outfile,
            field_info={
                'time': {
                    'transform': output.get_relative_timestamp,
                    'title': 'Updated'},
                'test_id': {'title': 'Test'},
            },
            fields=fields,
            rows=flat_sorted_statuses,
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
