"""This module contains functions to generate filter functions for handing
to dir_db commands."""

import argparse
import datetime as dt
import fnmatch
from pathlib import Path
from typing import Dict, Any, Callable

from pavilion import system_variables
from pavilion import utils
from pavilion.test_run import TestAttributes, TestRun, TestRunError

LOCAL_SYS_NAME = '<local_sys_name>'
TEST_FILTER_DEFAULTS = {
    'complete': False,
    'failed': False,
    'incomplete': False,
    'name': None,
    'newer-than': None,
    'older-than': None,
    'passed': False,
    'show-skipped': 'no',
    'sort-by': '-created',
    'sys-name': LOCAL_SYS_NAME,
    'user': utils.get_login(),
    'limit': None,
}

TEST_SORT_FUNCS = {
    'created': lambda test: test.created,
    'finished': lambda test: test.finished,
    'name': lambda test: test.name,
    'started': lambda test: test.started,
    'user': lambda test: test.user,
}


def add_test_filter_args(arg_parser: argparse.ArgumentParser,
                         default_overrides: Dict[str, Any] = None,
                         sort_functions: Dict[str, Callable] = None) -> None:
    """Add a common set of arguments for filtering tests (those supported by
    make_test_run_filter below).

    Arguments and defaults:

    {}

    :param arg_parser: The arg parser (or sub-parser) to add arguments to.
    :param default_overrides: A dictionary of defaults to override.
    :param sort_functions:
    """

    defaults = TEST_FILTER_DEFAULTS.copy()
    if default_overrides is not None:
        defaults.update(default_overrides)

    if sort_functions is None:
        sort_functions = TEST_SORT_FUNCS.copy()

    sort_options = (list(sort_functions.keys())
                    + ['-' + key for key in sort_functions.keys()])

    arg_parser.add_argument(
        '-l', '--limit', type=int, default=defaults['limit'],
        help="Max number of test runs to display.  Default: {}"
             .format(defaults['limit'])
    )
    arg_parser.add_argument(
        '--name', default=defaults['name'],
        help="Include only tests that match this name. Globbing wildcards are "
             "allowed. Default: {}"
             .format(defaults['name'])
    )
    arg_parser.add_argument(
        '--show-skipped', action='store', choices=('yes', 'no', 'only'),
        default=defaults['show-skipped'],
        help='Include skipped test runs.  Default: {}'
             .format(defaults['show-skipped']))

    arg_parser.add_argument(
        '--user', type=str, default=defaults['user'],
        help='Include only test runs started by this user. Default: {}'
             .format(defaults['user'])
    )
    pf_group = arg_parser.add_mutually_exclusive_group()
    pf_group.add_argument(
        '--passed', action='store_true', default=defaults['passed'],
        help='Include only passed test runs. Default: {}'
             .format(defaults['passed'])
    )
    pf_group.add_argument(
        '--failed', action='store_true', default=defaults['failed'],
        help='Include only failed test runs. Default: {}'
             .format(defaults['failed'])
    )
    ci_group = arg_parser.add_mutually_exclusive_group()
    ci_group.add_argument(
        '--complete', action='store_true', default=defaults['complete'],
        help='Include only completed test runs. Default: {}'
             .format(defaults['complete'])
    )
    ci_group.add_argument(
        '--incomplete', action='store_true',
        default=defaults['incomplete'],
        help='Include only test runs that are incomplete. Default: {}'
            .format(defaults['complete'])
    )
    arg_parser.add_argument(
        '--sys-name', type=str, default=defaults['sys-name'],
        help='Include only test runs that match the given system name, as '
             'presented by the sys.sys_name pavilion variable. '
             'Default: {}'.format(defaults['incomplete'])
    )
    arg_parser.add_argument(
        '--older-than', type=utils.hr_cutoff_to_datetime,
        default=defaults['older-than'],
        help=("Include only test runs older than (by start time) the given "
              "date or a time period given relative to the current date. \n\n"
              "This can be in the format a partial ISO 8601 timestamp "
              "(YYYY-MM-DDTHH:MM:SS), such as "
              "'2018', '1999-03-21', or '2020-05-03 14:32:02'\n\n"
              "Additionally, you can give an integer time distance into the "
              "past, such as '1 hour', '3months', or '2years'. "
              "(Whitespace between the number and unit is optional).\n"
              "Default: {}".format(defaults['older-than']))
    )
    arg_parser.add_argument(
        '--newer-than', type=utils.hr_cutoff_to_datetime,
        default=defaults['newer-than'],
        help='As per older-than, but include only tests newer than the given'
             'time.  Default: {}'.format(defaults['newer-than'])
    )
    arg_parser.add_argument(
        '--sort-by', type=str, default=defaults['sort-by'],
        choices=sort_options,
        help="How to sort the test. Ascending by default. Prepend a '-' to "
             "sort descending. This will also filter any items that "
             "don't have the sorted attribute. Default: {}"
             .format(defaults['sort-by'])
    )


add_test_filter_args.__doc__.format(
    '\n'.join(['    - {}: {}'.format(key, val)
               for key, val in TEST_FILTER_DEFAULTS.items()]))


def make_test_run_filter(
        complete: bool = False, failed: bool = False, incomplete: bool = False,
        name: str = None,
        newer_than: dt.datetime = None, older_than: dt.datetime = None,
        passed: bool = False, show_skipped: bool = False,
        sys_name: str = None, user: str = None):
    """Generate a filter function for use by dir_db.select and similar
    functions.

    :param complete: Only accept complete tests
    :param failed: Only accept failed tests
    :param incomplete: Only accept incomplete tests
    :param name: Only accept names that match this glob.
    :param newer_than: Only accept tests that are more recent than this date.
    :param older_than: Only accept tests older than this date.
    :param passed: Only accept passed tests
    :param show_skipped: Accept skipped tests.
    :param sys_name: Only accept tests with a matching sys_name.
    :param user: Only accept tests started by this user.
    :return:
    """

    if sys_name == LOCAL_SYS_NAME:
        sys_vars = system_variables.get_vars(defer=True)
        sys_name = sys_vars['sys_name']

    #  select once so we only make one filter.
    def filter_test_run(test_attrs: TestAttributes) -> bool:
        """Determine whether the test run at the given path should be
        included in the set."""

        if show_skipped == 'no' and test_attrs.skipped:
            return False
        elif show_skipped == 'only' and not test_attrs.skipped:
            return False

        if complete and not test_attrs.complete:
            return False

        if incomplete and test_attrs.complete:
            return False

        if user and test_attrs.user != user:
            return False

        if sys_name and sys_name != test_attrs.sys_name:
            return False

        if passed and test_attrs.result != TestRun.PASS:
            return False

        if failed and test_attrs.result != TestRun.FAIL:
            return False

        if older_than and test_attrs.started >= older_than:
            return False

        if newer_than and test_attrs.started <= newer_than:
            return False

        if name and not fnmatch.fnmatch(test_attrs.name, name):
            return False

        return True

    return filter_test_run


def make_test_sort_func(sort_name: str,
                        choices: Dict[str, Callable[[Any], Any]] = None) \
        -> (Callable[[Path], Any], bool):
    """Return a sort function and the sort order.

    :param sort_name: The name of the sort, possibly prepended with '-'.
    :param choices: A dictionary of sort order names and
        key functions (ala list.sort). Defaults to TEST_SORT_FUNCS
    """

    if choices is None:
        choices = TEST_SORT_FUNCS

    sort_asc = True
    if sort_name.startswith('-'):
        sort_asc = False
        sort_name = sort_name[1:]

    if sort_name not in choices:
        raise ValueError("Invalid sort name '{}'. Must be one of {}."
                         .format(sort_name, tuple(choices.keys())))

    return choices[sort_name], sort_asc
