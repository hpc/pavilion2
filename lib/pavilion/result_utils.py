"""A collection of utilities for getting the results of current and past
test runs and series."""

from concurrent.futures import ThreadPoolExecutor
from typing import List
import datetime

from pavilion import output
from pavilion.exceptions import TestRunError, TestRunNotFoundError, DeferredError
from pavilion.test_run import (TestRun)

# I suppose these are all the keys of the TestRun.results dict and the essential ones.
# I'm not sure which to use here or something else, discuss with reviewer.

BASE_FIELDS = [
    'id',
    'name',
    'started',
    'result'
]

timefields = ['created', 'started', 'finished', 'duration']

def get_result(test: TestRun):
    """Return the result for a single test_id.
    Add result_log (path) to results dictionary.
    :param test: The test to get results for
    """

    try:
        results = test.results
        for tf in timefields:
            if tf in results.keys():
                raw_key = tf+"_raw"
                results[raw_key] = results[tf]
                results[tf] = output.get_relative_timestamp(
                                        results[tf])
        results['results_log'] = test.results_log

    except (TestRunError, TestRunNotFoundError) as err:
        results = {'id': test.full_id}
        for field in BASE_FIELDS[1:]:
            results[field] = None

        results['result'] = "Test not found: {}".format(err)

    try:
        nodes = test.var_man.get('sched.test_nodes', '')
    except DeferredError:
        nodes = ''

    results['nodes'] = nodes
    return results


def get_results(pav_cfg, tests: List[TestRun]) -> List[dict]:
    """Return the results for all given test id's.

    :param pav_cfg: The Pavilion configuration.
    :param tests: Tests to get result for.
    """

    with ThreadPoolExecutor(max_workers=pav_cfg['max_threads']) as pool:
        return list(pool.map(get_result, tests))
