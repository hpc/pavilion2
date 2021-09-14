"""A collection of utilities for getting the results of current and past
test runs and series."""


import sys
import multiprocessing as mp
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
    'result'
]


def get_result(test_id, pav_conf):
    """Return the result for a single test_id.
    Add result_log (path) to results dictionary.
    :param pav_conf: The Pavilion config.
    :param test_id: The test id being queried.
    """

    try:
        test_full = TestRun.load(pav_conf, test_id)
        test = test_full.results
        test['results_log'] = test_full.results_log

    except (TestRunError, TestRunNotFoundError) as err:
        test = {'id': test_id}
        for field in BASE_FIELDS[1:]:
            test[field] = None

        test['result'] = "Test not found: {}".format(err)

    return test



def get_results(pav_cfg, test_ids, errfile=None):
    """Return the results for all given test id's.
    :param pav_cfg: The Pavilion config.
    :param List[str] test_ids: A list of test ids to load.
    :param errfile: Where to write standard error to.
    """

    test_ids = status_utils.get_tests(pav_cfg, test_ids, errfile=errfile)

    get_this_result = partial(get_result, pav_conf=pav_cfg)

    if sys.version_info.minor > 6:
        ncpu = min(config.NCPU, len(test_ids))
        mp_pool = mp.Pool(processes=ncpu)
        tests = mp_pool.map(get_this_result, test_ids)
    else:
        tests = map(get_this_result, test_ids)

    return tests
