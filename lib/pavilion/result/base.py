"""Handles getting the default, base results.

"""

import datetime

BASE_RESULTS = {
    'name': lambda test: test.name,
    'id': lambda test: test.id,
    'created': lambda test: datetime.datetime.fromtimestamp(
        test.path.stat().st_mtime).isoformat(" "),
    'started': lambda test: test.started.isoformat(" "),
    'finished': lambda test: test.finished.isoformat(" "),
    'duration': lambda test: str(test.finished - test.started),
    'user': lambda test: test.var_man['pav.user'],
    'job_id': lambda test: test.job_id,
    'sched': lambda test: test.var_man.as_dict().get('sched', {}),
    'sys_name': lambda test: test.var_man['sys.sys_name'],
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
        results[key] = func(test)

    return results
