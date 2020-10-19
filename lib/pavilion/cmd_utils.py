"""The module contains functions and classes that are generally useful across
multiple commands."""

from pavilion import dir_db
from pavilion.series import TestSeries, TestSeriesError
from pavilion.test_run import TestAttributes
from pavilion import filters

import argparse
from typing import List
from pathlib import Path


def arg_filtered_tests(pav_cfg, args: argparse.Namespace) -> List[int]:
    """Search for test runs that match based on the argument values in args,
    and return a list of matching test id's.

    Note: I know this violates the idea that we shouldn't be passing a
    generic object around and just using random bits of an undefined interface.
    BUT:

    1. The interface is well defined, by `filters.add_test_filter_args`.
    2. All of the used bits are *ALWAYS* used, so any errors will pop up
       immediately in unit tests.

    :param pav_cfg: The Pavilion config.
    :param args: An argument namespace with args defined by
        `filters.add_test_filter_args`, plus one additional `tests` argument
        that should contain a list of test id's, series id's, or the 'last'
        keyword.
    :return: A list of test id ints.
    """

    limit = args.limit

    filter_func = filters.make_test_run_filter(
        complete=args.complete,
        incomplete=args.incomplete,
        passed=args.passed,
        failed=args.failed,
        user=args.user,
        sys_name=args.sys_name,
        older_than=args.older_than,
        newer_than=args.newer_than,
        show_skipped=args.show_skipped,
    )

    order_func, order_asc = filters.get_sort_opts(
        sort_name=args.sort_by,
        choices=filters.TEST_SORT_FUNCS,
    )

    if args.tests:
        test_paths = test_list_to_paths(pav_cfg, args.tests)

        if args.force_filter:
            tests = dir_db.select_from(
                paths=test_paths,
                transform=TestAttributes,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=order_asc,
                limit=limit
            )
            test_ids = [test.id for test in tests]
        else:
            test_ids = dir_db.paths_to_ids(test_paths)

    else:
        tests = dir_db.select(
            id_dir=pav_cfg.working_dir / 'test_runs',
            transform=TestAttributes,
            filter_func=filter_func,
            order_func=order_func,
            order_asc=order_asc,
            limit=limit)[0]
        test_ids = [test.id for test in tests]

    return test_ids


def test_list_to_paths(pav_cfg, req_tests) -> List[Path]:
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
