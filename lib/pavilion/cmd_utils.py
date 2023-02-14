"""The module contains functions and classes that are generally useful across
multiple commands."""

import argparse
import datetime as dt
import io
import logging
import sys
import time
from pathlib import Path
from typing import List, TextIO
from collections import defaultdict

from pavilion import config
from pavilion import dir_db
from pavilion import filters
from pavilion import output
from pavilion import series
from pavilion import sys_vars
from pavilion import utils
from pavilion.errors import TestRunError, CommandError, TestSeriesError, PavilionError
from pavilion.test_run import TestRun, test_run_attr_transform, load_tests
from pavilion.types import ID_Pair

LOGGER = logging.getLogger(__name__)


def arg_filtered_tests(pav_cfg, args: argparse.Namespace,
                       verbose: TextIO = None) -> dir_db.SelectItems:
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
        or 'all' keyword. Last implies the last test series run by the current user
        on this system (and is the default if no tests are given. 'all' means all tests.
    :param verbose: A file like object to report test search status.
    :return: A list of test paths.
    """

    limit = args.limit
    verbose = verbose or io.StringIO()

    ids = []
    for test_range in args.tests:
        if '-' in test_range:
            id_start, id_end = test_range.split('-', 1)
            if id_start.startswith('s'):
                series_range_start = int(id_start.replace('s',''))
                if id_end.startswith('s'):
                    series_range_end = int(id_end.replace('s',''))
                else:
                    series_range_end = int(id_end)
                series_ids = range(series_range_start, series_range_end+1)
                for sid in series_ids:
                    ids.append('s' + str(sid))
            else:
                test_range_start = int(id_start)
                test_range_end = int(id_end)
                test_ids = range(test_range_start, test_range_end+1)
                for tid in test_ids:
                    ids.append(str(tid))
        else:
            ids.append(test_range)
    args.tests = ids

    if 'all' in args.tests:
        for arg, default in filters.TEST_FILTER_DEFAULTS.items():
            if hasattr(args, arg) and default != getattr(args, arg):
                break
        else:
            output.fprint(verbose, "Using default search filters: The current system, user, and "
                                   "newer_than 1 day ago.", color=output.CYAN)
            args.user = utils.get_login()
            args.newer_than = time.time() - dt.timedelta(days=1).total_seconds()
            args.sys_name = sys_vars.get_vars(defer=True).get('sys_name')

    filter_func = filters.make_test_run_filter(
        complete=args.complete,
        incomplete=args.incomplete,
        passed=args.passed,
        failed=args.failed,
        name=args.name,
        user=args.user,
        state=args.state,
        has_state=args.has_state,
        sys_name=args.sys_name,
        older_than=args.older_than,
        newer_than=args.newer_than,
    )

    order_func, order_asc = filters.get_sort_opts(args.sort_by, "TEST")

    if 'all' in args.tests:
        tests = dir_db.SelectItems([], [])
        working_dirs = set(map(lambda cfg: cfg['working_dir'],
                               pav_cfg.configs.values()))

        for working_dir in working_dirs:
            matching_tests = dir_db.select(
                pav_cfg,
                id_dir=working_dir / 'test_runs',
                transform=test_run_attr_transform,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=order_asc,
                verbose=verbose,
                limit=limit)

            tests.data.extend(matching_tests.data)
            tests.paths.extend(matching_tests.paths)

        return tests

    if not args.tests:
        args.tests.append('last')

    test_paths = test_list_to_paths(pav_cfg, args.tests, verbose)

    if not args.disable_filter:
        return dir_db.select_from(
            pav_cfg,
            paths=test_paths,
            transform=test_run_attr_transform,
            filter_func=filter_func,
            order_func=order_func,
            order_asc=order_asc,
            limit=limit
        )

    return dir_db.SelectItems(
        data=[test_run_attr_transform(path) for path in test_paths],
        paths=test_paths)


def arg_filtered_series(pav_cfg: config.PavConfig, args: argparse.Namespace,
                        verbose: TextIO = None) -> List[series.SeriesInfo]:
    """Return a list of SeriesInfo objects based on the args.series attribute. When args.series is
    empty, default to the 'last' series started by the user on this system. If 'all' is given,
    search all series (with a default current user/system/1-day filter) and additonally filtered
    by args attributes provied via filters.add_series_filter_args()."""

    limit = args.limit
    verbose = verbose or io.StringIO()

    if not args.series:
        args.series = ['last']

    if 'all' in args.series:
        for arg, default in filters.SERIES_FILTER_DEFAULTS.items():
            if hasattr(args, arg) and default != getattr(args, arg):
                break
        else:
            output.fprint(verbose, "Using default search filters: The current system, user, and "
                                   "newer_than 1 day ago.", color=output.CYAN)
            args.user = utils.get_login()
            args.newer_than = (dt.datetime.now() - dt.timedelta(days=1)).timestamp()
            args.sys_name = sys_vars.get_vars(defer=True).get('sys_name')

    matching_series = []
    seen_sids = []
    for sid in args.series:
        # Go through each provided sid (including last and all) and find all
        # matching series. Then only add them if we haven't seen them yet.
        if sid == 'last':
            sid = series.load_user_series_id(pav_cfg)
            if sid is None:
                return []

            found_series = [series.SeriesInfo.load(pav_cfg, sid)]

        elif sid == 'all':
            order_func, order_asc = filters.get_sort_opts(args.sort_by, 'SERIES')

            filter_func = filters.make_series_filter(
                complete=args.complete,
                has_state=args.has_state,
                incomplete=args.incomplete,
                name=args.name,
                newer_than=args.newer_than,
                older_than=args.older_than,
                state=args.state,
                sys_name=args.sys_name,
                user=args.user,
            )
            found_series = dir_db.select(
                pav_cfg=pav_cfg,
                id_dir=pav_cfg.working_dir/'series',
                filter_func=filter_func,
                transform=series.mk_series_info_transform(pav_cfg),
                order_func=order_func,
                order_asc=order_asc,
                use_index=False,
                verbose=verbose,
                limit=limit,
            ).data
        else:
            found_series = [series.SeriesInfo.load(pav_cfg, sid)]

        for sinfo in found_series:
            if sinfo.sid not in seen_sids:
                matching_series.append(sinfo)
                seen_sids.append(sinfo.sid)

        return matching_series


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
                    test = line.split('#')[0].strip()  # Removing any trailing comments.
                    tests.append(test)
        except OSError as err:
            raise ValueError("Could not read test list file at '{}': {}"
                             .format(path, err))

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
    for raw_id in req_tests:

        if raw_id == 'last':
            raw_id = series.load_user_series_id(pav_cfg, errfile)
            if raw_id is None:
                if errfile:
                    output.fprint(errfile, "User has no 'last' series for this machine.",
                                  color=output.YELLOW)
                continue

        if raw_id is None:
            continue

        if '.' not in raw_id and raw_id.startswith('s'):
            try:
                test_paths.extend(
                    series.list_series_tests(pav_cfg, raw_id))
            except TestSeriesError:
                if errfile:
                    output.fprint(errfile, "Invalid series id '{}'".format(raw_id),
                                  color=output.YELLOW)
        else:
            try:
                test_wd, _id = TestRun.parse_raw_id(pav_cfg, raw_id)
            except TestRunError as err:
                output.fprint(errfile, err, color=output.YELLOW)
                continue

            test_paths.append(test_wd/TestRun.RUN_DIR/str(_id))

    return test_paths


def _filter_tests_by_raw_id(pav_cfg, id_pairs: List[ID_Pair],
                            exclude_ids: List[str]) -> List[ID_Pair]:
    """Filter the given tests by raw id."""

    exclude_pairs = []

    for raw_id in exclude_ids:
        if '.' in raw_id:
            label, ex_id = raw_id.split('.', 1)
        else:
            label = 'main'
            ex_id = raw_id

        ex_wd = pav_cfg['configs'].get(label, None)
        if ex_wd is None:
            # Invalid label.
            continue

        ex_wd = Path(ex_wd)

        try:
            ex_id = int(ex_id)
        except ValueError:
            continue

        exclude_pairs.append((ex_wd, ex_id))

    return [pair for pair in id_pairs if pair not in exclude_pairs]


def get_tests_by_paths(pav_cfg, test_paths: List[Path], errfile: TextIO,
                       exclude_ids: List[str] = None) -> List[TestRun]:
    """Given a list of paths to test run directories, return the corresponding
    list of tests.

    :param pav_cfg: The pavilion configuration object.
    :param test_paths: The test run paths.
    :param errfile: Where to print warnings or errors.
    :param exclude_ids: A list of test raw id's to filter out.
    """

    test_pairs = []  # type: List[ID_Pair]

    for test_path in test_paths:
        if not test_path.exists():
            output.fprint(sys.stdout, "No test at path: {}".format(test_path))

        test_path = test_path.resolve()

        test_wd = test_path.parents[1]
        try:
            test_id = int(test_path.name)
        except ValueError:
            output.fprint(errfile, "Invalid test id '{}' from test path '{}'"
                          .format(test_path.name, test_path), color=output.YELLOW)
            continue

        test_pairs.append(ID_Pair((test_wd, test_id)))

    if exclude_ids:
        test_pairs = _filter_tests_by_raw_id(pav_cfg, test_pairs, exclude_ids)

    return load_tests(pav_cfg, test_pairs, errfile)


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
            raise CommandError("No tests specified and no last series was found.")

    # Convert series and test ids into test paths.
    test_id_pairs = []
    for raw_id in test_ids:
        # Series start with 's' (like 'snake') and never have labels
        if '.' not in raw_id and raw_id.startswith('s'):
            try:
                series_obj = series.TestSeries.load(pav_cfg, raw_id)
            except TestSeriesError as err:
                output.fprint(errfile, "Suite {} could not be found.\n{}"
                              .format(raw_id, err), color=output.RED)
                continue
            test_id_pairs.extend(list(series_obj.tests.keys()))

        # Just a plain test id.
        else:
            try:
                test_id_pairs.append(TestRun.parse_raw_id(pav_cfg, raw_id))

            except TestRunError as err:
                output.fprint(sys.stdout, "Error loading test '{}': {}"
                              .format(raw_id, err))

    if exclude_ids:
        test_id_pairs = _filter_tests_by_raw_id(pav_cfg, test_id_pairs, exclude_ids)

    return load_tests(pav_cfg, test_id_pairs, errfile)

def get_testset_name(tests: List['str'], files: List['str']):
    """Generate the name for the set set based on the test input to the run command.
    """
    # Expected Behavior:
    # pav run foo                   - 'foo'
    # pav run bar.a bar.b bar.c     - 'bar.*'
    # pav run -f some_file          - 'file:some_file'
    # pav run baz.a baz.b foo       - 'baz.*,foo'
    # pav run foo bar baz blarg     - 'foo,baz,bar,...'

    # First we get the list of files and a list of tests.
    # NOTE: If there is an intersection between tests in files and tests specified on command
    #       line, we remove the intersection from the list of tests
    #       For example, if some_test contains foo.a and foo.b
    #       pav run -f some_test foo.a foo.b will generate the test set file:some_test despite
    #       foo.a and foo.b being specified in both areas
    if files:
        files = [Path(filepath) for filepath in files]
        file_tests = cmd_utils.read_test_files([file.absolute() for file in files])
        tests = list(set(tests) - set(file_tests))

    # Here we generate a dictionary mapping tests to the suites they belong to
    # (Also the filenames)
    # This way we can name the test set based on suites rather than listing every test
    # Essentially, this dictionary will be reduced into a list of "globs" for the name
    test_set_dict = defaultdict(list)
    for test in tests:
        test_name_split = test.split('.')
        if len(test_name_split) == 2:
            suite_name, test_name = test_name_split
        elif len(test_name_split) == 1:
            suite_name = test
            test_name = None
        else:
            # TODO: Look through possible errors to find the proper one to raise here
            raise PavilionError(f"Test name not in suitename.testname format: {test}")


        if test_name:
            test_set_dict[suite_name].append(test_name)
        else:
            test_set_dict[suite_name] = None

    # Don't forget to add on the files!
    for file in files:
        test_set_dict[f'file:{file.name}'] = None

    # Reduce into a list of globs so we get foo.*, bar.*, etc.
    def get_glob(test_suite_name, test_names):
        if test_names is None:
            return test_suite_name

        num_names = len(test_names)
        if num_names == 1:
            return f'{test_suite_name}.{test_names[0]}'
        else:
            return f'{test_suite_name}.*'

    globs = [get_glob(test_suite, tests) for test_suite,tests in test_set_dict.items()]
    globs.sort(key=lambda glob: 0 if "file:" in glob else 1) # Sort the files to the front

    ntests_cutoff = 3 # If more than 3 tests in name, truncate and append '...'
    if len(globs) > ntests_cutoff:
        globs = globs[:ntests_cutoff+1]
        globs[ntests_cutoff] = '...'

    testset_name = ','.join(globs).rstrip(',')
    return testset_name
