"""The module contains functions and classes that are generally useful across
multiple commands."""

from pavilion import dir_db
from pavilion.series import TestSeries, TestSeriesError


def test_list_to_paths(pav_cfg, req_tests):
    """Given a list of test id's and series id's, return a list of paths
    to those tests.
    The keyword 'last' may also be given to get the last series run by
    the current user on the curren machine.

    :param pav_cfg: The Pavilion config.
    :param req_tests: A list of test id's, series id's, or 'last'.
    :return: A list of test id's.
    """

    test_paths = []
    for test_id in req_tests:

        if test_id == 'last':
            test_id = TestSeries.load_user_series_id(pav_cfg)

        if test_id.startswith('s'):
            try:
                test_paths.extend(
                    TestSeries.list_series_tests(pav_cfg, test_id))
            except TestSeriesError:
                raise ValueError("Invalid series id '{}'".format(test_id))

        else:
            try:
                test_id = int(test_id)
            except ValueError:
                raise ValueError("Invalid test id '{}'".format(test_id))

            test_dir = dir_db.make_id_path(
                pav_cfg.working_dir / 'test_runs', test_id)

            if not test_dir.exists():
                raise ValueError("No such test '{}'".format(test_id))

            test_paths.append(test_dir)

    return test_paths

