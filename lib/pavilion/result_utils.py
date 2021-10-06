"""A collection of utilities for getting the results of current and past
test runs and series."""


import sys
import multiprocessing as mp
from typing import List
from functools import partial

from pavilion import config
from pavilion import status_utils
from pavilion.test_run import (TestRun, TestRunError, TestRunNotFoundError)

# I suppose these are all the keys of the TestRun.results dict and the essential ones.
# I'm not sure which to use here or something else, discuss with reviewer.

BASE_FIELDS = [
    'id',
    'name',
    'sys_name',
    'started',
    'finished',
    'result',
    'results_log'
]


def get_result(test: TestRun):
    """Return the result for a single test_id.
    Add result_log (path) to results dictionary.
    :param test: The test to get results for
    """

    try:
        results = test.results
        results['results_log'] = test.results_log

    except (TestRunError, TestRunNotFoundError) as err:
        results = {'id': test.full_id}
        for field in BASE_FIELDS[1:]:
            results[field] = None

        results['result'] = "Test not found: {}".format(err)

    return results


def get_results(tests: List[TestRun]):
    """Return the results for all given test id's.
    :param tests: Tests to get result for.
    """

    if sys.version_info.minor > 6:
        ncpu = min(config.NCPU, len(tests))
        mp_pool = mp.Pool(processes=ncpu)
        tests = mp_pool.map(get_result, tests)
    else:
        tests = list(map(get_result, tests))

    return tests
