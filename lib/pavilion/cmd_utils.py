"""The module contains functions and classes that are generally useful across
multiple commands."""

import argparse
import logging
from pathlib import Path
from typing import List, TextIO

from pavilion import dir_db
from pavilion import exceptions
from pavilion import filters
from pavilion import output
from pavilion import series
from pavilion.test_run import TestRunError, \
    TestRun, test_run_attr_transform

LOGGER = logging.getLogger(__name__)


def arg_filtered_tests(pav_cfg, args: argparse.Namespace,
                       verbose: TextIO = None) -> List[Path]:
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
    :param verbose: A file like object to report test search status.
    :return: A list of test paths.
    """

    limit = args.limit

    filter_func = filters.make_test_run_filter(
        complete=args.complete,
        incomplete=args.incomplete,
        passed=args.passed,
        failed=args.failed,
        name=args.name,
        user=args.user,
        sys_name=args.sys_name,
        older_than=args.older_than,
        newer_than=args.newer_than,
        show_skipped=args.show_skipped,
    )

    order_func, order_asc = filters.get_sort_opts(args.sort_by, "TEST")

    if args.tests:
        test_paths = test_list_to_paths(pav_cfg, args.tests, verbose)

        if not args.disable_filter:
            test_paths = dir_db.select_from(
                paths=test_paths,
                transform=test_run_attr_transform,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=order_asc,
                limit=limit
            ).paths

    else:
        test_paths = []
        working_dirs = set(map(lambda cfg: cfg['working_dir'],
                               pav_cfg.configs.values()))

        for working_dir in working_dirs:
            matching_tests = dir_db.select(
                id_dir=working_dir / 'test_runs',
                transform=test_run_attr_transform,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=order_asc,
                verbose=verbose,
                limit=limit).paths

            test_paths.extend(matching_tests)

    return test_paths


def read_test_files(files: List[str]) -> List[str]:
    """Read the given files which contain a list of tests (removing comments)
    and return a list of test names."""

    tests = []
    for path in files:
        path = Path(path)
        try:
            with path.open() as file:
                for line in file:
                    line = line.strip()
                    if line.startswith('#'):
                        pass
                    test = line.split('#')[0].strip() # Removing any trailing comments.
                    tests.append(test)
        except OSError as err:
            raise ValueError("Could not read test list file at '{}': {}")

    return tests


def test_list_to_paths(pav_cfg, req_tests, errfile=None) -> List[Path]:
    """Given a list of raw test id's and series id's, return a list of paths
    to those tests.
    The keyword 'last' may also be given to get the last series run by
    the current user on the current machine.

    :param pav_cfg: The Pavilion config.
    :param req_tests: A list of test id's, series id's, or 'last'.
    :param errfile: An option output file for printing errors.
    :return: A list of test id's.
    """

    test_paths = []
    for test_id in req_tests:
        if test_id == 'last':
            test_id = series.load_user_series_id(pav_cfg)

        if '.' not in test_id and test_id.startswith('s'):
            try:
                test_paths.extend(
                    series.list_series_tests(pav_cfg, test_id))
            except series.errors.TestSeriesError:
                raise ValueError("Invalid series id '{}'".format(test_id))

        else:
            try:
                _, test_wd, _id = TestRun.parse_raw_id(pav_cfg, test_id)
            except TestRunError as err:
                output.fprint(err.args[0], file=errfile, color=output.YELLOW)
                continue

            test_paths.append(test_wd/TestRun.RUN_DIR/str(_id))

    return test_paths


def _filter_tests_by_raw_id(pav_cfg, tests: List[TestRun], exclude_ids: List[str]) \
        -> List[TestRun]:
    """Filter the given tests by raw id."""
    exclude_ids.sort()

    def _exclude_filter(test: TestRun):
        """Return False for any test in the exclude_ids list."""

        if (test.full_id in exclude_ids or
                (test.cfg_label == pav_cfg.default_label and
                 str(test.id) in exclude_ids)):
            return False
        else:
            return True

    return list(filter(_exclude_filter, tests))


def get_tests_by_paths(pav_cfg, test_paths: List[Path], errfile: TextIO,
                       exclude_ids: List[str] = None) -> List[TestRun]:
    """Given a list of paths to test run directories, return the corresponding
    list of tests.

    :param pav_cfg: The pavilion configuration object.
    :param test_paths: The test run paths.
    :param errfile: Where to print warnings or errors.
    :param exclude_ids: A list of test raw id's to filter out.
    """

    tests = []

    for test_path in test_paths:
        try:
            test_wd = test_path.parents[1]
            test_id = int(test_path.name)
            tests.append(TestRun.load(pav_cfg, test_wd, test_id))
        except TestRunError as err:
            output.fprint("Error loading test at '{}': {}"
                          .format(test_path, err.args[0]),
                          file=errfile)
        except ValueError:
            output.fprint("Invalid test id '{}' from test path '{}'"
                          .format(test_path.name, test_path),
                          file=errfile)

    if exclude_ids:
        tests = _filter_tests_by_raw_id(pav_cfg, tests, exclude_ids)

    return tests


def get_tests_by_id(pav_cfg, test_ids: List['str'], errfile: TextIO,
                    exclude_ids: List[str] = None) -> List[TestRun]:
    """Convert a list of raw test id's and series id's into a list of
    test objects.

    :param pav_cfg: The pavilion config
    :param test_ids: A list of tests or test series names.
    :param errfile: stream to output errors as needed
    :param exclude_ids: A list of raw test ids to prune from the test list.
    :return: List of test objects
    """

    test_ids = [str(test) for test in test_ids.copy()]

    if not test_ids:
        # Get the last series ran by this user
        series_id = series.load_user_series_id(pav_cfg)
        if series_id is not None:
            test_ids.append(series_id)
        else:
            raise exceptions.CommandError(
                "No tests specified and no last series was found."
            )

    test_list = []

    for test_id in test_ids:

        # Series start with 's' (like 'snake') and never have labels
        if '.' not in test_id and test_id.startswith('s'):
            try:
                test_list.extend(series.TestSeries.load(pav_cfg,
                                                        test_id).tests)
            except series.TestSeriesError as err:
                output.fprint(
                    "Suite {} could not be found.\n{}"
                    .format(test_id, err),
                    file=errfile,
                    color=output.RED
                )
                continue

        # Just a plain test id.
        else:
            try:
                test_list.append(TestRun.load_from_raw_id(pav_cfg, test_id))
            except TestRunError as err:
                output.fprint("Error loading test '{}': {}"
                              .format(test_id, err.args[0]))

    if exclude_ids:
        test_list = _filter_tests_by_raw_id(pav_cfg, test_list, exclude_ids)

    return test_list
