"""Handles getting the default, base results."""

import datetime

DISABLE_SCHED_KEYS = [
    'node_up_list',
    'node_avail_list',
    'node_list',
    'alloc_node_list',
]


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
    'name': lambda test: test.name,
    'id': lambda test: test.id,
    'test_version': lambda test: test.test_version,
    'pav_version': lambda test: test.var_man['pav.version'],
    'created': lambda test: datetime.datetime.fromtimestamp(
        test.path.stat().st_mtime).isoformat(" "),
    'started': lambda test: test.started.isoformat(" "),
    'finished': lambda test: test.finished.isoformat(" "),
    'duration': lambda test: str(test.finished - test.started),
    'user': lambda test: test.var_man['pav.user'],
    'job_id': lambda test: test.job_id,
    'sched': get_sched_keys,
    'sys_name': lambda test: test.var_man['sys.sys_name'],
    'pav_result_errors': lambda test: [],
    'return_value': None,
}
'''A dictionary of result key names and a function to acquire the value.
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

    for key, func in BASE_RESULTS.items():
        if func is not None:
            results[key] = func(test)

    return results


class ResultError(RuntimeError):
    """Error thrown when a failure occurs with any sort of result processing."""
