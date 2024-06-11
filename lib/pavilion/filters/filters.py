"""This module contains functions to generate filter functions for handing
to dir_db commands."""

import argparse
import datetime as dt
import fnmatch
import re
from functools import partial
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Callable, List, Union, Optional

from pavilion import series
from pavilion import utils
from pavilion.status_file import TestStatusFile, SeriesStatusFile, StatusError, \
    STATES, SERIES_STATES
from pavilion import sys_vars
from pavilion.test_run import TestRun
from pavilion import variables

from .transformer import FilterTransformer

from lark import Lark

GRAMMAR_PATH = Path(__file__).parent / 'filters.lark'

LOCAL_SYS_NAME = '<local_sys_name>'
TEST_FILTER_DEFAULTS = {
    'sort_by': '-created',
    'limit': None,
    'filter': None
}

SERIES_FILTER_DEFAULTS = {
    'limit': None,
    'sort_by': '-status_when',
    'filter': None
}

SORT_KEYS = {
    "TEST": ["created", "finished", "name", "started", "user", "id", ],
    "SERIES": ["created", "id", "status_when"]
}

STATE = "state"
HAS_STATE = "has_state"

CREATED = "created"
FINISHED = "finished"

NUM_NODES = "num_nodes"

HELP_TEXT = (
            "Filter requirements for tests and series.\n"
            "Example: pav status -F \"name=suite.test.* user=bob|user=jim complete\" \n"
            "Default filter: {} \n"
            "List of accepted operators: \n"
            "  AND                denoted by a space. \n"
            "  OR                 denoted by a '|'. \n"
            "  NOT                denoted by a '!'. \n\n"
            "List of accepted arguments: \n"
            "  COMPLETE           Include only completed test runs. \n"
            "  has_state:STATE    Include only {} who have had the \n"
            "                       given state at some point. \n"
            "  name=NAME          Include only tests/series that match this name. \n"
            "                       Globbing wildcards are allowed. \n"
            "  created<TIME       Include only {} that have been created before or after TIME. \n"
            "                       Both < and > comparators are accepted. \n"
            "                       date or a time period given relative to the current date. \n"
            "                       This can be in the format a partial ISO 8601 timestamp \n"
            "                       (YYYY-MM-DDTHH:MM:SS), such as \n"
            "                       '2018', '1999-03-21', or '2020-05-03 14:32:02' \n"
            "                       Additionally, you can give an integer time distance into the \n"
            "                       past, such as '1 hour', '3months', or '2years'. \n"
            "                       (Whitespace between the number and unit is optional). \n"
            "  finished<TIME      Include only {} that have finished before or after TIME. \n"
            "                       Both < and > comparators are accepted. \n"
            "  partition=PARTITION \n"
            "                     Include only {} that match this partition. \n"
            "  nodes:NODES        Include only {} that match NODES. Wildcards and ranges defined \n"
            "                       by brackets (i.e., node[001-005]) are allowed. \n"
            "  num_nodes>NUM_NODES \n"
            "                     Include only {} that have greater or less than NUM_NODES. \n"
            "                       Comparators <, >, and = are accepted. \n"
            "  STATE              Include only {} whose most recent state is the one given. \n"
            "                       States can be listed with 'pav show states' \n"
            "  sys_name=SYS_NAME  Include only {} that match the given system name, as \n"
            "                       presented by the sys.sys_name pavilion variable. \n"
            "  user=USER          Include only {} started by this user. \n")

filter_parser = Lark.open(GRAMMAR_PATH, start="query")
filter_trans = FilterTransformer()

def sort_func(test, choice):
    """Use partial to reduce inputs and use as key in sort function.
    Sort by default key if given key is invalid at this stage.
    :param test: Dict within list to sort on.
    :param choice: Key in dict to sort by.
    """

    return test[choice]

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

    target = "test_runs"
    help_text = HELP_TEXT + \
                ("  PASSED             Include only passed test runs. \n"
                 "  FAILED             Include only failed test runs. \n"
                 "  RESULT_ERROR       Include only test runs with a result error. \n"\
                 .format(defaults['filter'], target, target,
                        target, target, target, target, target,
                        target, target))

    arg_parser.add_argument(
        '-l', '--limit', type=int, default=defaults['limit'],
        help=("Max number of test_runs to display.  Default: {}"
              .format(defaults['limit']))

    )

    arg_parser.add_argument(
        '-F', '--filter', type=str, default=defaults['filter'],
        help=help_text)

    if sort_options:
        arg_parser.add_argument(
            '--sort-by', type=str, default=defaults['sort_by'],
            help=("How to sort the test_runs. Ascending by default. Prepend a '-' to "
                  "sort descending. This will also filter any items that "
                  "don't have the sorted attribute. Default: {}"
                  .format(defaults['sort_by']))
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

    target = "series"
    help_text = HELP_TEXT.format(defaults['filter'], target, target,
                    target, target, target, target, target, target,
                    target)

    arg_parser.add_argument(
        '-l', '--limit', type=int, default=defaults['limit'],
        help=("Max number of series to display.  Default: {}"
              .format(defaults['limit']))
    )

    arg_parser.add_argument(
        '-F', '--filter', type=str, default=defaults['filter'],
        help=help_text)

    if sort_options:
        arg_parser.add_argument(
            '--sort-by', type=str, default=defaults['sort_by'],
            help=("How to sort the series. Ascending by default. Prepend a '-' to "
                  "sort descending. This will also filter any items that "
                  "don't have the sorted attribute. Default: {}"
                  .format(defaults['sort_by']))
        )

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

def parse_query(query: str) -> Callable[[Dict], bool]:
    tree = filter_parser.parse(query)
    res = filter_trans.transform(tree)

    return res
