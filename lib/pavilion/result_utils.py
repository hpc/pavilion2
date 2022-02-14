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
        for tfields in timefields:
            if tfields in results.keys():
                raw_key = tfields+"_raw"
                results[raw_key] = results[tfields]
                results[tfields] = output.get_relative_timestamp(
                                        results[tfields])

        results['results_log'] = test.results_log.as_posix()

    except (TestRunError, TestRunNotFoundError) as err:
        results = {'id': test.full_id}
        for field in BASE_FIELDS[1:]:
            results[field] = None

        results['result'] = "Test not found: {}".format(err)

    return results


def get_results(pav_cfg, tests: List[TestRun]) -> List[dict]:
    """Return the results for all given test id's.

    :param pav_cfg: The Pavilion configuration.
    :param tests: Tests to get result for.
    """

    with ThreadPoolExecutor(max_workers=pav_cfg['max_threads']) as pool:
        return list(pool.map(get_result, tests))


def printkeys(keydict):
    """ Print the keys collected by key list """
    print("AVAILABLE KEYS:")
    for key, val in sorted(keydict.items()):
        if not val:
            continue
        print('\t', key+':')
        for sval in sorted(val):
            print('\t\t', sval)
    return 0


def keylist(results):
    """ Called when the --list-keys flag is present in the results command.
        Takes a list of flattened results dictionaries.
        Prints out the available key options.

        Sorts the key options into:
        - Default keys
        - Common keys: Available for all given tests
        - Test keys: Available for at least one of the variants of this
        particular test included in the given tests.
        Any of these tests can be passed to the key flag.
    """
    klist = {}
    if not isinstance(results, list):
        results = list(results)

    for res in results:
        keyset = set([res for res, val in res.items() 
                      if not isinstance(val, list)])
        dkey = res["name"].split('.')[0]
        if dkey not in klist.keys():
            klist[dkey] = keyset
        else:
            ks = keyset.union(klist[dkey])
            klist.update({dkey: ks})

    if len(klist.keys()) == 1:
        printkeys(klist)
        return 0

    vals = list(klist.values())
    common_keys = vals[0].intersection(*vals[1:])
    base_set = set(BASE_FIELDS)
    kfinal = {"--DEFAULT": base_set}

    for key, val in klist.items():
        test_keys = val.difference(common_keys)
        if test_keys:
            kfinal[key] = test_keys
    common_keys = common_keys.difference(base_set)
    kfinal['-common'] = common_keys
    printkeys(kfinal)

    return 0
