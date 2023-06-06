"""This module contains functions to generate filter functions for handing
to dir_db commands."""

import argparse
import datetime as dt
import fnmatch
from functools import partial
from pathlib import Path
from typing import Dict, Any, Callable, List

from pavilion import series
from pavilion import utils
from pavilion.status_file import TestStatusFile, SeriesStatusFile, StatusError
from pavilion.sys_vars import base_classes
from pavilion.test_run import TestRun

LOCAL_SYS_NAME = '<local_sys_name>'
TEST_FILTER_DEFAULTS = {
    'complete': False,
    'failed': False,
    'has_state': None,
    'incomplete': False,
    'name': None,
    'newer_than': None,
    'older_than': None,
    'passed': False,
    'result_error': False,
    'sort_by': '-created',
    'state': None,
    'sys_name': None,
    'user': None,
    'limit': None,
}

SORT_KEYS = {
    "TEST": ["created", "finished", "name", "started", "user", "id", ],
    "SERIES": ["created", "id", "status_when"]
}


def sort_func(test, choice):
    """Use partial to reduce inputs and use as key in sort function.
    Sort by default key if given key is invalid at this stage.
    :param test: Dict within list to sort on.
    :param choice: Key in dict to sort by.
    """

    return test[choice]


def add_common_filter_args(target: str,
                           arg_parser: argparse.ArgumentParser,
                           defaults: dict,
                           sort_options: List[str],
                           disable_opts: List[str]):
    """Add common arguments for all filters.

    :param target: The name of what is being filtered, to be inserted
        in documentation. Should be plural.
    :param arg_parser: The argparser to add arguments to.
    :param defaults: A dictionary of default values for all arguments.
    :param sort_options: A list of possible sort options.
    :param disable_opts: Options to disable.

    :return:
    """

    if 'complete' not in disable_opts and 'incomplete' not in disable_opts:
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
    if 'has-state' not in disable_opts:
        arg_parser.add_argument(
            '--has-state', type=str, default=defaults['state'],
            help="Include only {} who have had the given state at some point."
                 "Default: {}".format(target, defaults['has_state'])
        )
    arg_parser.add_argument(
        '-l', '--limit', type=int, default=defaults['limit'],
        help=("Max number of {} to display.  Default: {}"
              .format(target, defaults['limit']))

    )
    if 'name' not in disable_opts:
        arg_parser.add_argument(
            '--name', default=defaults['name'],
            help=("Include only tests/series that match this name. Globbing wildcards are "
                  "allowed. Default: {}"
                  .format(defaults['name']))
        )
    if 'older-than' not in disable_opts:
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
    if 'newer-than' not in disable_opts:
        arg_parser.add_argument(
            '--newer-than', type=utils.hr_cutoff_to_ts,
            default=defaults['newer_than'],
            help='As per older-than, but include only {} newer than the given'
                 'time.  Default: {}'.format(target, defaults['newer_than'])
        )
    if 'state' not in disable_opts:
        arg_parser.add_argument(
            '--state', type=str, default=defaults['state'],
            help="Include only {} whose most recent state is the one given. "
                 "Default: {}".format(target, defaults['state'])
        )
    if 'sys-name' not in disable_opts:
        arg_parser.add_argument(
            '--sys-name', type=str, default=defaults['sys_name'],
            help='Include only {} that match the given system name, as '
                 'presented by the sys.sys_name pavilion variable. '
                 'Default: {}'.format(target, defaults['sys_name'])
        )
    if 'user' not in disable_opts:
        arg_parser.add_argument(
            '--user', type=str, default=defaults['user'],
            help='Include only {} started by this user. Default: {}'
            .format(target, defaults['user'])
        )
    if sort_options:
        arg_parser.add_argument(
            '--sort-by', type=str, default=defaults['sort_by'],
            help=("How to sort the {}. Ascending by default. Prepend a '-' to "
                  "sort descending. This will also filter any items that "
                  "don't have the sorted attribute. Default: {}"
                  .format(target, defaults['sort_by']))
        )


def add_test_filter_args(arg_parser: argparse.ArgumentParser,
                         default_overrides: Dict[str, Any] = None,
                         sort_keys: List[str] = None,
                         disable_opts: List[str] = None) -> None:
    """Add a common set of arguments for filtering tests (those supported by
    make_test_run_filter below).

    Arguments and defaults:

    {}

    :param arg_parser: The arg parser (or sub-parser) to add arguments to.
    :param default_overrides: A dictionary of defaults to override.
    :param sort_keys: A list of sort-by names, corresponding to keys in the data being sorted.
    :param disable_opts: Options to disable (not attach to the arg_parser).
    """

    disable_opts = disable_opts or []

    defaults = TEST_FILTER_DEFAULTS.copy()
    if default_overrides is not None:
        defaults.update(default_overrides)

        for ovr_key in default_overrides:
            if ovr_key not in TEST_FILTER_DEFAULTS:
                raise RuntimeError(
                    "Included default override for key that doesn't exist. {}"
                    .format(ovr_key)
                )

    if sort_keys is None:
        sort_keys = SORT_KEYS['TEST']

    sort_options = (sort_keys
                    + ['-' + key for key in sort_keys])

    add_common_filter_args("test runs", arg_parser, defaults, sort_options, disable_opts)

    pf_group = arg_parser.add_mutually_exclusive_group()
    if 'passed' not in disable_opts:
        pf_group.add_argument(
            '--passed', action='store_true', default=defaults['passed'],
            help=('Include only passed test runs. Default: {}'
                  .format(defaults['passed']))
        )
    if 'failed' not in disable_opts:
        pf_group.add_argument(
            '--failed', action='store_true', default=defaults['failed'],
            help=('Include only failed test runs. Default: {}'
                  .format(defaults['failed']))
        )
    if 'result-error' not in disable_opts:
        pf_group.add_argument(
            '--result-error', action='store_true',
            default=defaults['result_error'],
            help=('Include only test runs with a result error. Default: {}'
                  .format(defaults['result_error']))
        )


add_test_filter_args.__doc__.format(
    '\n'.join(['    - {}: {}'.format(key, val)
               for key, val in TEST_FILTER_DEFAULTS.items()]))


def add_series_filter_args(arg_parser: argparse.ArgumentParser,
                           default_overrides: Dict[str, Any] = None,
                           sort_keys: List[str] = None,
                           disable_opts: List[str] = None) -> None:
    """Add a common set of arguments for filtering series (those supported by
    make_series_filter below).

    Arguments and defaults:

    {}

    :param arg_parser: The arg parser (or sub-parser) to add arguments to.
    :param default_overrides: A dictionary of defaults to override.
    :param sort_keys: A list of sort-by names.
    :param disable_opts: Don't include the listed options.
    """

    disable_opts = disable_opts or []

    defaults = SERIES_FILTER_DEFAULTS.copy()
    if default_overrides is not None:
        defaults.update(default_overrides)

        for ovr_key in default_overrides:
            if ovr_key not in SERIES_FILTER_DEFAULTS:
                raise RuntimeError(
                    "Included default override for key that doesn't exist. {}"
                    .format(ovr_key)
                )

    if sort_keys is None:
        sort_keys = SORT_KEYS["SERIES"]

    sort_options = (sort_keys
                    + ['-' + key for key in sort_keys])

    add_common_filter_args("series", arg_parser, defaults, sort_options, disable_opts)


def filter_test_run(
        test_attrs: Dict, complete: bool, failed: bool, has_state: str,
        incomplete: bool, name: str, newer_than: float, older_than: float, passed: bool,
        result_error: bool, state: str, sys_name: str, user: str):
    """Determine whether the test run at the given path should be
    included in the set. This function with test_attrs as the sole input is
    returned by make_test_run_filter.

    :param test_attrs: Dict of attributes filtered to determine whether to
        keep or discard test.
    :param complete: Only accept complete tests
    :param failed: Only accept failed tests
    :param has_state: Only accept tests that have had the given state.
    :param incomplete: Only accept incomplete tests
    :param name: Only accept names that match this glob.
    :param newer_than: Only accept tests that are more recent than this date.
    :param older_than: Only accept tests older than this date.
    :param passed: Only accept passed tests
    :param result_error: Only accept tests with a result error.
    :param state: Only accept tests whose state is the one given.
    :param sys_name: Only accept tests with a matching sys_name.
    :param user: Only accept tests started by this user.
    :return:
    """

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

    if older_than is not None and test_attrs.get('created') > older_than:
        return False

    if newer_than is not None and test_attrs.get('created') < newer_than:
        return False

    test_name = test_attrs.get('name') or ''
    if name and not fnmatch.fnmatch(test_name, name):
        return False

    if state is not None or has_state is not None:
        status_file_path = Path(test_attrs['path'])/TestRun.STATUS_FN
        try:
            status_file = TestStatusFile(status_file_path)
        except StatusError:
            # Couldn't open status file, so it can't have the given state...
            return False

        if state is not None and not state.upper() == status_file.current().state:
            return False
        elif has_state is not None and not status_file.has_state(has_state.upper()):
            return False

    return True


def make_test_run_filter(
        complete: bool = False, failed: bool = False, has_state: str = None,
        incomplete: bool = False, name: str = None,
        newer_than: float = None, older_than: float = None,
        passed: bool = False, result_error: bool = False, state: str = None,
        sys_name: str = None, user: str = None):
    """Generate a filter function for use by dir_db.select and similar
    functions. This operates on TestAttribute objects, so make sure to
    pass the TestAttribute class as the transform to dir_db functions.

    :param complete: Only accept complete tests
    :param failed: Only accept failed tests
    :param has_state: Only accept tests that have had this state at some point.
    :param incomplete: Only accept incomplete tests
    :param name: Only accept names that match this glob.
    :param newer_than: Only accept tests that are more recent than this date.
    :param older_than: Only accept tests older than this date.
    :param passed: Only accept passed tests
    :param result_error: Only accept tests with a result error.
    :param state: Only accept tests with this as the current state.
    :param sys_name: Only accept tests with a matching sys_name.
    :param user: Only accept tests started by this user.
    :return:
    """

    if sys_name == LOCAL_SYS_NAME:
        sys_vars = base_classes.get_vars(defer=True)
        sys_name = sys_vars['sys_name']

    filter_func = partial(
        filter_test_run,
        complete=complete, failed=failed, has_state=has_state,
        incomplete=incomplete, name=name,
        newer_than=newer_than, older_than=older_than, passed=passed,
        result_error=result_error, state=state, sys_name=sys_name,
        user=user)

    return filter_func


def get_sort_opts(
        sort_name: str,
        stype: str) -> (Callable[[Path], Any], bool):
    """Return a sort function and sort order.

    :param sort_name: The name of the sort, possibly prepended with -.
    :param stype: TEST or SERIES to select the list of options available
        for sort_name.
    """

    sort_key = TEST_FILTER_DEFAULTS['sort_by']
    if stype in SORT_KEYS.keys():
        if sort_name.strip('-') in SORT_KEYS[stype]:
            sort_key=sort_name

    sort_ascending = True
    if sort_key.startswith('-'):
        sort_ascending = False
        sort_key = sort_key[1:]

    sortf = partial(sort_func, choice=sort_key)

    return sortf, sort_ascending


SERIES_FILTER_DEFAULTS = {
    'complete': False,
    'has_state': None,
    'incomplete': False,
    'limit': None,
    'name': None,
    'newer_than': None,
    'older_than': None,
    'sort_by': '-status_when',
    'state': None,
    'sys_name': None,
    'user': None,
}


def make_series_filter(complete: bool = False, has_state: str = None,
                       incomplete: bool = False, name: str = None,
                       newer_than: float = None,
                       older_than: float = None, state: str = None,
                       sys_name: str = None, user: str = None) \
                    -> Callable[[series.SeriesInfo], bool]:
    """Generate a filter for using with dir_db functions to filter series. This
    is expected to operate on series.SeriesInfo objects, so make sure to pass
    Series info as the dir_db transform function.

    :param complete: Only accept series for which all tests are complete.
    :param has_state: Only accept tests that have had the given state.
    :param incomplete: Only accept series for which not all tests are complete.
    :param name: Only accept series whose name matches the given glob.
    :param newer_than: Only accept series created after this time.
    :param older_than: Only accept series created before this time.
    :param state: Only accept series with the given state.
    :param sys_name: Only accept series created on this system.
    :param user: Only accept series created by this user.
    """

    if sys_name == LOCAL_SYS_NAME:
        sys_vars = base_classes.get_vars(defer=True)
        sys_name = sys_vars['sys_name']

    def series_filter(sinfo: series.SeriesInfo):
        """Generated series filter function."""

        if user is not None and sinfo['user'] != user:
            return False

        created = sinfo.get('created')
        if newer_than and created < newer_than:
            return False

        if older_than and created > older_than:
            return False

        if complete and not sinfo.get('complete'):
            return False

        if incomplete and sinfo.get('complete'):
            return False

        if name:
            series_name = sinfo.get('name')
            if not fnmatch.fnmatch(series_name, name):
                return False

        if sys_name and sinfo.get('sys_name') != sys_name:
            return False

        if state or has_state:
            series_status_path = Path(sinfo['path']) / series.STATUS_FN
            try:
                series_status = SeriesStatusFile(series_status_path)
            except StatusError:
                # Couldn't get a status to check.
                return False

            if state and not state.upper() == series_status.current().state:
                return False
            elif has_state and not series_status.has_state(has_state):
                return False

        return True

    return series_filter
