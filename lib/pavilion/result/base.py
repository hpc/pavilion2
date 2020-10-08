"""Handles getting the default, base results."""

import datetime

DISABLE_SCHED_KEYS = [
    'node_up_list',
    'node_avail_list',
    'node_list',
    'alloc_node_list',
    'test_node_list',
]

RESULT_ERRORS = 'pav_result_errors'


def get_sched_keys(test):
    """Return the sched section keys. Keys whose name ends in 'list' will
    always be a list, otherwise they'll be single items. Keys in
    DISABLE_SCHED_KEYS won't be added."""

    sched_keys = {}

    for key, value in test.var_man.as_dict().get('sched', {}).items():
        if key in DISABLE_SCHED_KEYS:
            continue

        if isinstance(value, list) and len(value) > 1 or key.endswith('_list'):
            sched_keys[key] = value
        else:
            sched_keys[key] = value[0] if value else None

    return sched_keys


BASE_RESULTS = {
    'name': (lambda test: test.name,
             "The test run name"),
    'id': (lambda test: test.id,
           "The test run id"),
    'test_version': (lambda test: test.test_version,
                     "The test config version."),
    'pav_version': (lambda test: test.var_man['pav.version'],
                    "The version of Pavilion used to run this test."),
    'created': (lambda test: datetime.datetime.fromtimestamp(
                test.path.stat().st_mtime).isoformat(" "),
                "When the test was created."),
    'started': (lambda test: test.started.isoformat(" "),
                "When the test run itself started."),
    'finished': (lambda test: test.finished.isoformat(" "),
                 "When the test run finished."),
    'duration': (lambda test: (test.finished - test.started).total_seconds(),
                 "Duration of the test run (finished - started) in seconds."),
    'user': (lambda test: test.var_man['pav.user'],
             "The user that started the test."),
    'job_id': (lambda test: test.job_id,
               "The scheduler plugin's jobid for the test."),
    'sched': (get_sched_keys,
              "Most of the scheduler variables."),
    'sys_name': (lambda test: test.var_man['sys.sys_name'],
                 "The system name '{{sys.sys_name}}'"),
    RESULT_ERRORS: (lambda test: [],
                    "Errors from processing results."),
    'per_file': (lambda test: {},
                 "Per file results."),
    'return_value': (None,
                     "The return value of run.sh"),
    'uuid': (lambda test: test.uuid,
             "The test's fully unique identifier.")
}
'''A dictionary of result key names and a tuple of the function to acquire the
value and a documentation string.
The function should take a test_run object as it's only argument. If the
function is None, that denotes that this key is reserved, but filled in
elsewhere.
'''


def base_results(test) -> dict:
    """Get all of the auto-filled result values for a test.
    :param pavilion.test_run.PavTestRun test: A pavilion test object.
    :return: A dictionary of result values.
    """

    results = {}

    for key, (func, doc) in BASE_RESULTS.items():
        if func is not None:
            results[key] = func(test)

    return results
