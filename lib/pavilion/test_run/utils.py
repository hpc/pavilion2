"""Utility functions for test run objects."""

from concurrent.futures import ThreadPoolExecutor
from typing import List, TextIO

from pavilion import dir_db, output
from pavilion.exceptions import TestRunError
from pavilion.types import ID_Pair
from .test_run import TestRun


def get_latest_tests(pav_cfg, limit):
    """Returns ID's of latest test given a limit

:param pav_cfg: Pavilion config file
:param int limit: maximum size of list of test ID's
:return: list of test ID's
:rtype: list(int)
"""

    test_dir_list = []
    runs_dir = pav_cfg.working_dir/TestRun.RUN_DIR
    for test_dir in dir_db.select(pav_cfg, runs_dir).paths:
        mtime = test_dir.stat().st_mtime
        try:
            test_id = int(test_dir.name)
        except ValueError:
            continue

        test_dir_list.append((mtime, test_id))

    test_dir_list.sort()
    return [test_id for _, test_id in test_dir_list[-limit:]]


def _load_test(pav_cfg, id_pair: ID_Pair):
    """Load a test object from an ID_Pair."""

    test_wd, test_id = id_pair

    return TestRun.load(pav_cfg, test_wd, test_id)


LOADED_TESTS = {}


def load_tests(pav_cfg, id_pairs: List[ID_Pair], errfile: TextIO) -> List['TestRun']:
    """Load a set of tests in parallel.

    :raises TestRunError: When loading a test fails
    """

    id_pairs = set(id_pairs)

    tests = []

    # Only load tests that haven't already been loaded.
    not_loaded = []
    for pair in id_pairs:
        if pair in LOADED_TESTS:
            tests.append(LOADED_TESTS[pair])
        else:
            not_loaded.append(pair)
    id_pairs = not_loaded

    with ThreadPoolExecutor(max_workers=pav_cfg['max_threads']) as pool:
        results = []
        for id_pair in id_pairs:
            results.append(pool.submit(_load_test, pav_cfg, id_pair))

        for result in results:
            try:
                tests.append(result.result())
            except TestRunError as err:
                output.fprint(
                    "Error loading test: {}".format(err.args[0]),
                    color=output.YELLOW, file=errfile)

    return tests
