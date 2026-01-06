"""The module contains functions and classes that are generally useful across
multiple commands."""

import datetime as dt
import io
import logging
import sys
import time
import os
from pathlib import Path
from argparse import Namespace
from typing import List, TextIO, Union, Iterator, Optional, Callable
from collections import defaultdict

from pavilion import config
from pavilion import dir_db
from pavilion import filters
from pavilion import groups
from pavilion import output
from pavilion import sys_vars
from pavilion import utils
from pavilion.series import TestSeries, SeriesInfo, list_series_tests, mk_series_info_transform
from pavilion.id_utils import load_user_series_id, resolve_relative_id
from pavilion.errors import TestRunError, CommandError, TestSeriesError, \
                            PavilionError, TestGroupError
from pavilion.test_run import TestRun, load_tests, TestAttributes
from pavilion.test_ids import TestID, SeriesID, ID
from pavilion.types import ID_Pair
from pavilion.micro import flatten

LOGGER = logging.getLogger(__name__)


def load_last_series(pav_cfg: config.PavConfig, errfile: TextIO) -> Optional[TestSeries]:
    """Load the series object for the last series run by this user on this system."""

    try:
        series_id = load_user_series_id(pav_cfg)
    except TestSeriesError as err:
        output.fprint(errfile, "Failed to find last series: {}".format(err.args[0]),
                      color=output.YELLOW)
        return None

    if series_id is None:
        output.fprint(errfile, "Failed to find last series.", color=output.YELLOW)
        return None

    try:
        return TestSeries.load(pav_cfg, series_id)
    except TestSeriesError as err:
        output.fprint(errfile, "Failed to load last series: {}".format(err.args[0]))
        return None

def arg_filtered_tests(pav_cfg: config.PavConfig,
                       tests: List[TestID],
                       series: List[SeriesID],
                       filter_query: Optional[str] = None,
                       sort_by: Optional[str] = None,
                       limit: Optional[int] = None,
                       verbose: Optional[TextIO] = None) -> dir_db.SelectItems:
    """Search for test runs that match based on the specified tests and series IDs,
    and return a list of matching test id's.

    :param pav_cfg: The Pavilion config.
    :param tests: A list of test IDs on which to filter.
    :param series: A list of series IDs whose tests should be filtered.
    :param limit: The maximum number of test runs to return.
    :param sort_by: The field on which to sort.
    :param filter_query: The query to use when filtering tests.
    :param verbose: A file like object to report test search status.
    :return: A list of test paths.
    """

    verbose = verbose or io.StringIO()
    sort_by = sort_by or "-created"

    use_default_filter = True

    if sort_by != "-created" or limit is not None or filter_query is not None:
        use_default_filter = False

    if SeriesID("all") in series and use_default_filter:
        output.fprint(verbose, "Using default search filters: The current system, user, and "
                               "created less than 1 day ago.", color=output.CYAN)
        filter_query = make_filter_query()

    if filter_query is None:
        filter_func = filters.const(True) # Always return True
    else:
        try:
            filter_func = filters.parse_query(filter_query)
        except filters.FilterParseError:
            raise PavilionError(f"Invalid syntax in filter query: {filter_query}")

    order_func, order_asc = filters.get_sort_opts(sort_by, "TEST")

    if SeriesID("all") in series:
        tests = dir_db.SelectItems([], [])
        working_dirs = set(map(lambda cfg: cfg['working_dir'],
                               pav_cfg.configs.values()))

        for working_dir in working_dirs:
            matching_tests = dir_db.select(
                pav_cfg,
                id_dir=working_dir / 'test_runs',
                transform=TestAttributes,
                filter_func=filter_func,
                order_func=order_func,
                order_asc=order_asc,
                verbose=verbose,
                limit=limit)

            tests.data.extend(matching_tests.data)
            tests.paths.extend(matching_tests.paths)

        return tests

    test_paths = test_list_to_paths(pav_cfg, tests, verbose)

    for sid in series:
        if sid.last():
            sid_ = load_user_series_id(pav_cfg, errfile=verbose)

            if sid_ is None:
                output.fprint(verbose, "No last series found.")
                continue
        else:
            sid_ = sid

        test_paths.extend(map(lambda x: x.resolve(), list_series_tests(pav_cfg, sid_)))

    return dir_db.select_from(
        pav_cfg,
        paths=test_paths,
        transform=TestAttributes,
        filter_func=filter_func,
        order_func=order_func,
        order_asc=order_asc,
        limit=limit
    )

def make_filter_query() -> str:
    """Construct the default filter query, which targets tests created
    by the current user on the current system more recently than 1 day ago."""

    template = 'user={} and created>1 day'

    user = utils.get_login()
    sysname = sys_vars.get_vars(defer=True).get('sys_name')

    fargs = [user]

    if sysname is not None and len(sysname) > 0:
        template += ' and sys_name={}'
        fargs.append(sysname)

    return template.format(*fargs)


def arg_filtered_series(pav_cfg: config.PavConfig,
                        series: List[SeriesID],
                        filter_query: Optional[str] = None,
                        sort_by: Optional[str] = None,
                        limit: Optional[int] = None,
                        verbose: Optional[TextIO] = None) -> List[SeriesInfo]:
    """Return a list of SeriesInfo objects based on the args.series attribute. When args.series is
    empty, default to the 'last' series started by the user on this system. If 'all' is given,
    search all series (with a default current user/system/1-day filter) and additonally filtered
    by args attributes provied via filters.add_series_filter_args()."""

    verbose = verbose or io.StringIO()
    sort_by = sort_by or "-status_when"

    use_default_filter = True

    if sort_by != "-status_when" or limit is not None or filter_query is not None:
        use_default_filter = False

    if SeriesID("all") in series and use_default_filter:
        output.fprint(verbose, "Using default search filters: The current system, user, and "
                                "created less than 1 day ago.", color=output.CYAN)
        filter_query = make_filter_query()

    seen_sids = []
    found_series = []

    for sid in series:
        # Go through each provided sid (including last and all) and find all
        # matching series. Then only add them if we haven't seen them yet.
        if sid.last():
            last_series = load_last_series(pav_cfg, verbose)
            if last_series is None:
                return []

            found_series.append(last_series.info())

        elif sid.all():
            order_func, order_asc = filters.get_sort_opts(sort_by, 'SERIES')

            if filter_query is None:
                filter_func = filters.const(True)  # Always return True
            else:
                try:
                    filter_func = filters.parse_query(filter_query)
                except filters.FilterParseError:
                    raise PavilionError(f"Invalid syntax in filter query: {filter_query}")

            found_series = dir_db.select(
                pav_cfg=pav_cfg,
                id_dir=pav_cfg.working_dir/'series',
                filter_func=filter_func,
                transform=mk_series_info_transform(pav_cfg),
                order_func=order_func,
                order_asc=order_asc,
                use_index=False,
                verbose=verbose,
                limit=limit,
            ).data
        else:
            found_series.append(SeriesInfo.load(pav_cfg, sid))

    matching_series = []
    for sinfo in found_series:
        if sinfo.id not in seen_sids:
            matching_series.append(sinfo)
            seen_sids.append(sinfo.id)

    return matching_series


def read_test_files(pav_cfg: config.PavConfig, files: List[str]) -> List[str]:
    """Read the given files which contain a list of tests (removing comments)
    and return a list of test names."""

    tests = []
    for path in files:
        path = Path(path)

        if path.name == path.as_posix() and not path.exists():
            # If a plain filename is given (with not path components) and it doesn't
            # exist in the CWD, check to see if it's a saved collection.
            path = get_collection_path(pav_cfg, path)

            if path is None:
                raise PavilionError(
                    "Cannot find collection '{}' in the config dirs nor the current dir."
                    .format(collection))

        try:
            with path.open() as file:
                for line in file:
                    line = line.strip()
                    if line.startswith('#'):
                        pass
                    test = line.split('#')[0].strip()  # Removing any trailing comments.
                    tests.append(test)
        except OSError as err:
            raise PavilionError("Could not read test list file at '{}'"
                                .format(path), prior_error=err)

    return tests


def get_collection_path(pav_cfg: config.PavConfig, collection: str) -> Optional[Path]:
    """Find a collection in one of the config directories. Returns None on failure."""

    # Check if this collection exists in one of the defined config dirs
    for config in pav_cfg['configs'].items():
        _, config_path = config
        collection_path = config_path.path / 'collections' / collection
        if collection_path.exists():
            return collection_path

    return None


def test_list_to_paths(pav_cfg: config.PavConfig, req_tests: List[Union[ID]],
                        errfile: Optional[TextIO] = None) -> List[Path]:
    """Given a list of test id's and series id's, return a list of paths
    to those tests.
    The keyword 'last' may also be given to get the last series run by
    the current user on the current machine.

    :param pav_cfg: The Pavilion config.
    :param req_tests: A list of test id's, series id's, or 'last'.
    :param errfile: An option output file for printing errors.
    :return: A list of test paths.
    """

    if errfile is None:
        errfile = io.StringIO()

    test_paths = []
    for raw_id in req_tests:

        if isinstance(raw_id, SeriesID) and raw_id.last():
            raw_id = load_user_series_id(pav_cfg, errfile)
            if raw_id is None:
                output.fprint(errfile, "User has no 'last' series for this machine.",
                              color=output.YELLOW)
                continue

        if isinstance(raw_id, TestID):
            try:
                test_wd, _id = TestRun.parse_raw_id(pav_cfg, raw_id)
            except TestRunError as err:
                output.fprint(errfile, err, color=output.YELLOW)
                continue

            if raw_id.is_relative():
                raw_id = resolve_relative_id(pav_cfg, test_wd, raw_id)

            test_path = test_wd/TestRun.RUN_DIR/str(raw_id)
            test_paths.append(test_path)
            if not test_path.exists():
                output.fprint(errfile,
                              "Test run with id '{}' could not be found.".format(raw_id),
                              color=output.YELLOW)
        elif isinstance(raw_id, SeriesID):
            try:
                test_paths.extend(
                    list_series_tests(pav_cfg, raw_id))
            except TestSeriesError:
                output.fprint(errfile, "Invalid series id '{}'".format(raw_id),
                              color=output.YELLOW)
        else:
            # A group
            try:
                group = groups.TestGroup(pav_cfg, raw_id)
            except TestGroupError as err:
                output.fprint(
                    errfile,
                    "Invalid test group id '{}'.\n{}"
                    .format(raw_id, err.pformat()))
                continue

            if not group.exists():
                output.fprint(
                    errfile,
                    "Group '{}' does not exist.".format(raw_id))
                continue

            try:
                test_paths.extend(group.tests())
            except TestGroupError as err:
                output.fprint(
                    errfile,
                    "Invalid test group id '{}', could not get tests from group."
                    .format(raw_id))

    return test_paths


def _filter_tests_by_raw_id(pav_cfg: config.PavConfig, id_pairs: List[ID_Pair],
                            exclude_ids: List[TestID]) -> List[ID_Pair]:
    """Filter the given tests by raw id."""

    exclude_pairs = []

    ex_wd = Path(pav_cfg.get("working_dir"))

    exclude_pairs = [ID_Pair(ex_wd, id) for id in exclude_ids]

    return [pair for pair in id_pairs if pair not in exclude_pairs]


def get_tests_by_paths(pav_cfg: config.PavConfig, test_paths: List[Path], errfile: TextIO,
                       exclude_ids: List[TestID] = None) -> List[TestRun]:
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
        test_id = TestID(test_path.name)

        test_pairs.append(ID_Pair((test_wd, test_id)))

    if exclude_ids:
        test_pairs = _filter_tests_by_raw_id(pav_cfg, test_pairs, exclude_ids)

    return load_tests(pav_cfg, test_pairs, errfile)


def get_tests_by_id(pav_cfg: config.PavConfig, test_ids: List[Union[TestID, SeriesID]],
                    errfile: TextIO, exclude_ids: Optional[List[TestID]] = None) -> List[TestRun]:
    """Convert a list of raw test id's and series id's into a list of
    test objects.

    :param pav_cfg: The pavilion config
    :param test_ids: A list of tests or test series names.
    :param errfile: stream to output errors as needed
    :param exclude_ids: A list of raw test ids to prune from the test list.
    :return: List of test objects
    """

    # Convert series and test ids into test paths.
    test_id_pairs = []
    for raw_id in test_ids:
        # Series start with 's' (like 'snake') and never have labels
        if isinstance(raw_id, SeriesID):
            try:
                if raw_id.last():
                    series_obj = load_last_series(pav_cfg, errfile)
                else:
                    series_obj = TestSeries.load(pav_cfg, raw_id)
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

def get_testset_name(pav_cfg: config.PavConfig, tests: List[str], files: List[str]) -> str:
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
        file_tests = read_test_files(pav_cfg, files)
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


def get_last_test_id(pav_cfg: config.PavConfig, errfile: TextIO) -> Optional[TestID]:
    """Get the ID of the last run test, if it exists, and if there is a single
    unambigous last test. If there is not, return None."""

    last_series = load_last_series(pav_cfg, errfile)

    if last_series is None:
        return None

    id_pairs = list(last_series.tests.keys())

    if len(id_pairs) == 0:
        output.fprint(
            errfile,
            f"Most recent series contains no tests.",
            color=output.YELLOW)
        return None

    if len(id_pairs) > 1:
        output.fprint(
            errfile,
            f"Multiple tests exist in last series. Could not unambiguously identify last test.",
            color=output.YELLOW)
        return None

    return TestID(str(id_pairs[0][1]))

def list_files(path: Path, include_root: bool = False) -> Iterator[Path]:
    """Recursively list all files in a directory, optionally including the directory itself."""

    for root, dirs, files in os.walk(path):
        if include_root:
            yield Path(root)

        for fname in files:
            yield Path(root) / fname
        for dname in dirs:
            yield Path(root) / dname
