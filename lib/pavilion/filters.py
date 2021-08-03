"""This module contains functions to generate filter functions for handing
to dir_db commands."""

import argparse
import datetime as dt
import time
import fnmatch
from pathlib import Path
from functools import partial

from typing import Dict, Any, Callable, List

from pavilion import system_variables
from pavilion import utils
from pavilion.test_run import TestRun

LOCAL_SYS_NAME = '<local_sys_name>'
TEST_FILTER_DEFAULTS = {
    'complete': False,
    'failed': False,
    'incomplete': False,
    'name': None,
    'newer_than': time.time() - dt.timedelta(days=1).total_seconds(),
    'older_than': None,
    'passed': False,
    'result_error': False,
    'show_skipped': 'no',
    'sort_by': '-created',
    'sys_name': LOCAL_SYS_NAME,
    'user': utils.get_login(),
    'limit': None,
    'disable_filter': False,
}

SORT_KEYS = {
    "TEST": ["created", "finished", "name", "started", "user", "id"],
    "SERIES": ["created", "id"]
}

def sort_func(test, choice, sort_type):
    """Use partial to reduce inputs and use as key in sort function.
    :param test: Dict within list to sort on.
    :param choice: Key in dict to sort by.
    :param sort_type: Type of list of dicts to sort by, check for key.
    """

    if sort_type not in SORT_KEYS.keys():
        return None
    elif choice not in SORT_KEYS[sort_type]:
        return None
    else:
        return test[choice]

def add_common_filter_args(target: str,
                           arg_parser: argparse.ArgumentParser,
                           defaults: dict,
                           sort_options: List[str]):
    """Add common arguments for all filters.

    :param target: The name of what is being filtered, to be inserted
        in documentation. Should be plural.
    :param arg_parser: The argparser to add arguments to.
    :param defaults: A dictionary of default values for all arguments.
    :param sort_options: A list of possible sort options.

    :return:
    """
    ci_group = arg_parser.add_mutually_exclusive_group()
    ci_group.add_argument(
        '--complete', action='store_true', default=defaults['complete'],
        help=('Include only completed test runs. Default: {}'
              .format(defaults['complete']))
    )
    ci_group.add_argument(
        '--incomplete', action='store_true',
        default=defaults['incomplete'],
        help=('Include only test runs that are incomplete. Default: {}'
              .format(defaults['complete']))
    )
    arg_parser.add_argument(
        '-l', '--limit', type=int, default=defaults['limit'],
        help=("Max number of {} to display.  Default: {}"
              .format(target, defaults['limit']))

    )
    arg_parser.add_argument(
        '--older-than', type=utils.hr_cutoff_to_ts,
        default=defaults['older_than'],
        help=("Include only {} older than (by creation time) the given "
              "date or a time period given relative to the current date. \n\n"
              "This can be in the format a partial ISO 8601 timestamp "
              "(YYYY-MM-DDTHH:MM:SS), such as "
              "'2018', '1999-03-21', or '2020-05-03 14:32:02'\n\n"
              "Additionally, you can give an integer time distance into the "
              "past, such as '1 hour', '3months', or '2years'. "
              "(Whitespace between the number and unit is optional).\n"
              "Default: {}".format(target, defaults['older_than']))
    )
    arg_parser.add_argument(
        '--newer-than', type=utils.hr_cutoff_to_ts,
        default=defaults['newer_than'],
        help='As per older-than, but include only {} newer than the given'
             'time.  Default: {}'.format(target, defaults['newer_than'])
    )
    arg_parser.add_argument(
        '--sys-name', type=str, default=defaults['sys_name'],
        help='Include only {} that match the given system name, as '
             'presented by the sys.sys_name pavilion variable. '
             'Default: {}'.format(target, defaults['sys_name'])
    )
    arg_parser.add_argument(
        '--user', type=str, default=defaults['user'],
        help='Include only {} started by this user. Default: {}'
        .format(target, defaults['user'])
    )
    if sort_options:
        arg_parser.add_argument(
            '--sort-by', type=str, default=defaults['sort_by'],
            choices=sort_options,
            help=("How to sort the {}. Ascending by default. Prepend a '-' to "
                  "sort descending. This will also filter any items that "
                  "don't have the sorted attribute. Default: {}"
                  .format(target, defaults['sort_by']))
        )


def add_test_filter_args(arg_parser: argparse.ArgumentParser,
                         default_overrides: Dict[str, Any] = None,
                         sort_functions: Dict[str, Callable] = None) -> None:
    """Add a common set of arguments for filtering tests (those supported by
    make_test_run_filter below).

    Arguments and defaults:

    {}

    :param arg_parser: The arg parser (or sub-parser) to add arguments to.
    :param default_overrides: A dictionary of defaults to override.
    :param sort_functions: A dict of sort-by names and sorting functions. The
        functions don't matter at this point. If empty, sorting is disabled.
    """

    defaults = TEST_FILTER_DEFAULTS.copy()
    if default_overrides is not None:
        defaults.update(default_overrides)

        for ovr_key in default_overrides:
            if ovr_key not in TEST_FILTER_DEFAULTS:
                raise RuntimeError(
                    "Included default override for key that doesn't exist. {}"
                    .format(ovr_key)
                )

    if sort_functions is None:
        sort_functions = SORT_KEYS['TEST']

    sort_options = (sort_functions
                    + ['-' + key for key in sort_functions])

    add_common_filter_args("test runs", arg_parser, defaults, sort_options)

    arg_parser.add_argument(
        '--name', default=defaults['name'],
        help=("Include only tests that match this name. Globbing wildcards are "
              "allowed. Default: {}"
              .format(defaults['name']))
    )
    arg_parser.add_argument(
        '--show-skipped', action='store', choices=('yes', 'no', 'only'),
        default=defaults['show_skipped'],
        help=('Include skipped test runs.  Default: {}'
              .format(defaults['show_skipped'])))

    pf_group = arg_parser.add_mutually_exclusive_group()
    pf_group.add_argument(
        '--passed', action='store_true', default=defaults['passed'],
        help=('Include only passed test runs. Default: {}'
              .format(defaults['passed']))
    )
    pf_group.add_argument(
        '--failed', action='store_true', default=defaults['failed'],
        help=('Include only failed test runs. Default: {}'
              .format(defaults['failed']))
    )
    pf_group.add_argument(
        '--result-error', action='store_true',
        default=defaults['result_error'],
        help=('Include only test runs with a result error. Default: {}'
              .format(defaults['result_error']))
    )
    arg_parser.add_argument(
        '--disable-filter', default=False, action='store_true',
        help="Disable filtering for tests that are specifically "
             "requested."
    )


add_test_filter_args.__doc__.format(
    '\n'.join(['    - {}: {}'.format(key, val)
               for key, val in TEST_FILTER_DEFAULTS.items()]))


def add_series_filter_args(arg_parser: argparse.ArgumentParser,
                           default_overrides: Dict[str, Any] = None,
                           sort_functions: Dict[str, Callable] = None) -> None:
    """Add a common set of arguments for filtering series (those supported by
    make_series_filter below).

    Arguments and defaults:

    {}

    :param arg_parser: The arg parser (or sub-parser) to add arguments to.
    :param default_overrides: A dictionary of defaults to override.
    :param sort_functions: A dict of sort-by names and sorting functions. The
        functions don't matter at this point. If empty, sorting is disabled.
    """

    defaults = SERIES_FILTER_DEFAULTS.copy()
    if default_overrides is not None:
        defaults.update(default_overrides)

        for ovr_key in default_overrides:
            if ovr_key not in SERIES_FILTER_DEFAULTS:
                raise RuntimeError(
                    "Included default override for key that doesn't exist. {}"
                    .format(ovr_key)
                )

    if sort_functions is None:
        sort_functions = SORT_KEYS["SERIES"]

    sort_options = (sort_functions
                    + ['-' + key for key in sort_functions])

    add_common_filter_args("series", arg_parser, defaults, sort_options)


def filter_test_run(
        test_attrs: Dict, complete: bool, failed: bool, incomplete: bool,
        name: str, newer_than: float, older_than: float, passed: bool,
        result_error: bool, show_skipped: bool, sys_name: str, user: str):
    """Determine whether the test run at the given path should be
    included in the set. This function with test_attrs as the sole input is
    returned by make_test_run_filter.

    :param test_attrs: Dict of attributes filtered to determine whether to
        keep or discard test.
    :param complete: Only accept complete tests
    :param failed: Only accept failed tests
    :param incomplete: Only accept incomplete tests
    :param name: Only accept names that match this glob.
    :param newer_than: Only accept tests that are more recent than this date.
    :param older_than: Only accept tests older than this date.
    :param passed: Only accept passed tests
    :param result_error: Only accept tests with a result error.
    :param show_skipped: Accept skipped tests.
    :param sys_name: Only accept tests with a matching sys_name.
    :param user: Only accept tests started by this user.
    :return:
    """

    if show_skipped == 'no' and test_attrs.get('skipped'):
        return False
    elif show_skipped == 'only' and not test_attrs.get('skipped'):
        return False

    if complete and not test_attrs.get('complete'):
        return False

    if incomplete and test_attrs.get('complete'):
        return False

    if user and test_attrs.get('user') != user:
        return False

    if sys_name and test_attrs.get('sys_name') != sys_name:
        return False

    if passed and test_attrs.get('result') != TestRun.PASS:
        return False

    if failed and test_attrs.get('result') != TestRun.FAIL:
        return False

    if result_error and test_attrs.get('result') != TestRun.ERROR:
        return False

    if older_than is not None and test_attrs.get('created') > newer_than:
        return False

    if newer_than is not None and test_attrs.get('created') < newer_than:
        return False

    if name and not fnmatch.fnmatch(test_attrs.get('name'), name):
        return False

    return True


def make_test_run_filter(
        complete: bool = False, failed: bool = False, incomplete: bool = False,
        name: str = None,
        newer_than: float = None, older_than: float = None,
        passed: bool = False, result_error: bool = False,
        show_skipped: bool = False, sys_name: str = None, user: str = None):
    """Generate a filter function for use by dir_db.select and similar
    functions. This operates on TestAttribute objects, so make sure to
    pass the TestAttribute class as the transform to dir_db functions.

    :param complete: Only accept complete tests
    :param failed: Only accept failed tests
    :param incomplete: Only accept incomplete tests
    :param name: Only accept names that match this glob.
    :param newer_than: Only accept tests that are more recent than this date.
    :param older_than: Only accept tests older than this date.
    :param passed: Only accept passed tests
    :param result_error: Only accept tests with a result error.
    :param show_skipped: Accept skipped tests.
    :param sys_name: Only accept tests with a matching sys_name.
    :param user: Only accept tests started by this user.
    :return:
    """

    if sys_name == LOCAL_SYS_NAME:
        sys_vars = system_variables.get_vars(defer=True)
        sys_name = sys_vars['sys_name']

    filter_func = partial(filter_test_run, complete=complete, failed=failed, incomplete=incomplete,
                  name=name, newer_than=newer_than, older_than=older_than, passed=passed,
                  rslte=result_error, show_skipped=show_skipped, sys_name=sys_name, user=user)

    return filter_func


def get_sort_opts(
        sort_name: str,
        stype: str) -> (Callable[[Path], Any], bool):
    """Return a sort function and sort order.

    :param sort_name: The name of the sort, possibly prepended with -.
    :param stype: TEST or SERIES to select the list of options available
        for sort_name.
    """

    sort_ascending = True
    if sort_name.startswith('-'):
        sort_ascending = False
        sort_name = sort_name[1:]

    sortf = partial(sort_func, choice=sort_name, sort_type=stype)

    return sortf, sort_ascending


SERIES_FILTER_DEFAULTS = {
    'limit': None,
    'sort_by': '-created',
    'complete': False,
    'incomplete': False,
    'newer_than': time.time() - dt.timedelta(days=1).total_seconds(),
    'older_than': None,
    'sys_name': LOCAL_SYS_NAME,
    'user': utils.get_login(),
}


def make_series_filter(
        user: str = None, sys_name: str = None, newer_than: dt.datetime = None,
        older_than: dt.datetime = None, complete: bool = False,
        incomplete: bool = False) -> Callable[[Dict[str, Any]], bool]:
    """Generate a filter for using with dir_db functions to filter series. This
    is expected to operate on series.SeriesInfo objects, so make sure to pass
    Series info as the dir_db transform function.

    :param complete: Only accept series for which all tests are complete.
    :param incomplete: Only accept series for which not all tests are complete.
    :param newer_than: Only accept series created after this time.
    :param older_than: Only accept series created before this time.
    :param sys_name: Only accept series created on this system.
    :param user: Only accept series created by this user.
    """

    if sys_name == LOCAL_SYS_NAME:
        sys_vars = system_variables.get_vars(defer=True)
        sys_name = sys_vars['sys_name']

    def series_filter(series: Dict[str, Any]):
        """Generated series filter function."""

        if user is not None and series['user'] != user:
            return False

        if newer_than and series.get('created') < newer_than:
            return False

        if older_than and series.get('created') > older_than:
            return False

        if complete and not series.get('complete'):
            return False

        if incomplete and series.get('complete'):
            return False

        if sys_name and series.get('sys_name') != sys_name:
            return False

        return True

    return series_filter
