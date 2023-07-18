"""This module contains functions to generate filter functions for handing
to dir_db commands."""

# pylint: disable=C0103

import argparse
import datetime as dt
import fnmatch
import re
from functools import partial
from pathlib import Path
from typing import Dict, Any, Callable, List, Union

from pavilion import series
from pavilion import utils
from pavilion.status_file import TestStatusFile, SeriesStatusFile, StatusError, \
    STATES, SERIES_STATES
from pavilion.sys_vars import base_classes
from pavilion.test_run import TestRun

LOCAL_SYS_NAME = '<local_sys_name>'
TEST_FILTER_DEFAULTS = {
    'sort_by': '-created',
    'limit': None,
    'disable_filter': False,
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

FUNC = 0
OPS  = 1

OP_EQ  = '='
OP_LT  = '<'
OP_GT  = '>'
OP_OR  = '|'
OP_AND = ' '
OP_NOT = '!'

STATE = "state"
HAS_STATE = "has_state"

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
    help_text = "Filter requirements for tests and series.\n"\
                "Default filter: {} \n"\
                "List of accepted operators: \n"\
                "AND denoted by a space. \n"\
                "OR denoted by a '|'. \n"\
                "NOT denoted by a '!'. \n\n"\
                "List of accepted arguments: \n"\
                "complete: Include only completed test runs. \n"\
                "has_state=STATE: Include only {} who have had the "\
                "given state at some point. \n"\
                "name=NAME: Include only tests/series that match this name. "\
                "Globbing wildcards are allowed. \n"\
                "older_than=TIME: Include only {} older than (by creation time) the given "\
                "date or a time period given relative to the current date. \n\n"\
                "This can be in the format a partial ISO 8601 timestamp "\
                "(YYYY-MM-DDTHH:MM:SS), such as "\
                "'2018', '1999-03-21', or '2020-05-03 14:32:02' \n\n"\
                "Additionally, you can give an integer time distance into the "\
                "past, such as '1 hour', '3months', or '2years'. "\
                "(Whitespace between the number and unit is optional). \n"\
                "newer_than=TIME: Include only {} whose most recent state "\
                "is the one given. \n"\
                "STATE: Include only {} whose most recent state is the one given. "\
                "sys_name=SYS_NAME: Include only {} that match the given system name, as "\
                "presented by the sys.sys_name pavilion variable. \n"\
                "user=USER: Include only {} started by this user. \n"\

    if defaults == TEST_FILTER_DEFAULTS:
        help_text = help_text + \
                    "passed: Not compatible with series. Include only passed test runs. \n"\
                    "failed: Not compatible with series. Include only failed test runs. \n"\
                    "result_error: Not compatible with series. Include only test runs \n"\
                    "with a result error. \n"\
                    .format(defaults['filter'], target, target,
                            target, target, target, target)
    else:
        help_text = help_text\
                    .format(defaults['filter'], target, target,
                            target, target, target, target)



    arg_parser.add_argument(
        '-l', '--limit', type=int, default=defaults['limit'],
        help=("Max number of {} to display.  Default: {}"
              .format(target, defaults['limit']))

    )

    arg_parser.add_argument(
        '-F', '--filter', type=str, default=defaults['filter'],
        help=help_text)

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

def complete(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "complete" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "complete" attribute
    """
    return attrs.get('complete')

def name(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "name" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "name" attribute
    """
    name_parse = re.compile(r'^([a-zA-Z0-9_*?\[\]-]+)'  # The test suite name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?'  # The test name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?$'  # The permutation name.
                            )
    test_name = attrs.get('name') or ''
    val_match = name_parse.match(val)
    name_match = name_parse.match(test_name)

    if val_match is not None:
        suite, test, perm = val_match.groups()

    if name_match is not None:
        _, _, test_perm = name_match.groups()

        if not test_perm:
            test_name = test_name + '.*'

    if suite is None:
        suite = '*'

    if test is None:
        test = '*'

    if perm is None:
        perm = '*'

    new_val = '.'.join([suite, test, perm])
    return fnmatch.fnmatch(test_name, new_val)

def user(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "user" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "user" attribute
    """
    return attrs.get('user') == val

def sys_name(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "sys_name" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "sys_name" attribute
    """
    if val == LOCAL_SYS_NAME:
        sys_vars = base_classes.get_vars(defer=True)
        val = sys_vars['sys_name']

    return attrs.get('sys_name') == val

def passed(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "passed" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "passed" attribute
    """
    return attrs.get('result') == TestRun.PASS

def failed(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "failed" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "failed" attribute
    """
    return attrs.get('result') == TestRun.FAIL

def result_error(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return "result_error" status of a test

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "result_error" attribute
    """
    return attrs.get('result') == TestRun.ERROR

def older_than(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return whether "created" status of a test is older than a given time

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "created" attribute being older than a given time
    """
    try:
        time_val = float(val)
    except:
        raise ValueError('Invalid time entry for older_than: {}'.format(val))

    return attrs.get('created') < float(time_val)

def newer_than(attrs: Union[Dict, series.SeriesInfo], op: str, val: str) -> bool:
    """Return whether "complete" status of a test is new than a given time

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query, if applicable
    :param val: the value of the filter query, if applicable

    :return: result of the test or series "complete" attribute being newer than a given time
    """
    try:
        time_val = float(val)
    except:
        raise ValueError('Invalid time entry for newer_than: {}'.format(val))

    return attrs.get('created') > float(time_val)

def state(attrs: Union[Dict, series.SeriesInfo], key: str, val: str, status_file) -> bool:
    """Return "state" status of a test

    :param attrs: attributes of a given test or series
    :param val: the state query
    :param val: status file function of either the series or the test

    :return: result of the test or series "state"
    """
    if status_file is TestStatusFile:
        status_path = Path(attrs['path'])/TestRun.STATUS_FN
    else:
        status_path = Path(attrs['path'])/series.STATUS_FN

    try:
        status = status_file(status_path)
    except StatusError:
        return False

    if key == STATE and val.upper() != status.current().state:
        return False
    elif key == HAS_STATE and not status.has_state(val.upper()):
        return False

    return True

SERIES_FUNCS = {
    'complete': [complete, ''],
    'name': [name, '='],
    'user': [user, '='],
    'sys_name': [sys_name, '='],
    'older_than': [older_than, '='],
    'newer_than': [newer_than, '='],
}

TEST_FUNCS = {
    'complete': [complete, ''],
    'name': [name, '='],
    'user': [user, '='],
    'sys_name': [sys_name, '='],
    'result_error': [result_error, ''],
    'older_than': [older_than, '='],
    'newer_than': [newer_than, '='],
    'passed': [passed, ''],
    'failed': [failed, ''],
}

def NOT(op: str, attrs: Union[Dict, series.SeriesInfo], funcs: Dict) -> bool:
    """Perform a not operation

    :param op: target operand
    :param attrs: attributes of a given test or series
    :param funcs: respective functions for tests or series

    :return: result of the not evaluation on the operand
    """
    if op and op[0] == '!':
        return not filter_run(attrs, funcs, op.strip(OP_NOT))
    else:
        raise SyntaxError("Incorrect '!' operator syntax")

def OR(op1: str, op2: str, attrs: Union[Dict, series.SeriesInfo], funcs: Dict) -> bool:
    """Perform an or operation

    :param op1: first target operand
    :param op2: second target operand
    :param attrs: attributes of a given test or series
    :param funcs: respective functions for tests or series

    :return: result of the or evaluation on the operands
    """
    if op1 and op2:
        return filter_run(attrs, funcs, op1) or filter_run(attrs, funcs, op2)
    else:
        raise SyntaxError("Incorrect '|' operator syntax")

def AND(op1: str, op2: str, attrs: Union[Dict, series.SeriesInfo], funcs: Dict) -> bool:
    """Perform an and operation

    :param op1: first target operand
    :param op2: second target operand
    :param attrs: attributes of a given test or series
    :param funcs: respective functions for tests or series

    :return: result of the and evaluation on the operands
    """
    return filter_run(attrs, funcs, op1) and filter_run(attrs, funcs, op2)

def trim(target: str) -> str:
    """Remove excess spaces from the target

    :param target: filter query string

    :return: the whitespace-trimmed query
    """
    return re.sub(r' +([|!=<>]) +', r'\1', target).strip(' ')

def parse_target(target: str) -> (str, Union[str, None], Union[str, None]):
    """Parse the key, operand, and value apart. If there is not an
       operand or value, return the target

    :param target: filter query keyword argument

    :return: the key, operand, and value if applicable, otherwise the target
    """
    for op in [OP_EQ, OP_LT, OP_GT]:
        if op in target:
            key, val = target.split(op, 1)
            return (key, op, val)

    return (target, '', '')

def filter_run(test_attrs: Union[Dict, series.SeriesInfo], funcs: Dict, target: str) -> bool:
    """Main logic of the filter. Evaluate arguments and apply any operations to them.

    :param test_attrs: attributes of a given test or series
    :param funcs: respective functions for tests or series
    :param target: filter query string

    :return: whether a particular test passes the filter query requirements
    """

    if target is None:
        return True
    else:
        target = trim(target)
        if target == '':
            return True

    if OP_AND in target:
        op1, op2 = target.split(OP_AND, 1)
        return AND(op1, op2, test_attrs, funcs)

    elif OP_OR in target:
        op1, op2 = target.split(OP_OR, 1)
        return OR(op1, op2, test_attrs, funcs)

    else:
        if OP_NOT in target:
            return NOT(target, test_attrs, funcs)

        else:
            key, op, val = parse_target(target)

            if key in funcs and op in funcs[key][OPS]:
                return funcs[key][FUNC](test_attrs, op, val)
            elif key in STATES.list() and funcs == TEST_FUNCS:
                return state(test_attrs, STATE, key, TestStatusFile)
            elif key in SERIES_STATES.list() and funcs == SERIES_FUNCS:
                return state(test_attrs, STATE, key, SeriesStatusFile)
            elif key == HAS_STATE and funcs == TEST_FUNCS:
                return state(test_attrs, HAS_STATE, val, TestStatusFile)
            elif key == HAS_STATE and funcs == SERIES_FUNCS:
                return state(test_attrs, HAS_STATE, val, SeriesStatusFile)
            else:
                raise ValueError(
                    "Keyword {} not recognized.".format(key))

def make_test_run_filter(target: str) -> Callable[[Dict], bool]:
    """Generate a filter function for use by dir_db.select and similar
    functions. This operates on TestAttribute objects, so make sure to
    pass the TestAttribute class as the transform to dir_db functions.

    :param target: Filter query string, contains all filter requirements

    :return: a partial function that takes a set of test attributes
    """
    filter_func = partial(
        filter_run,
        funcs=TEST_FUNCS,
        target=target)

    return filter_func

def make_series_filter(target: str) -> Callable[[Dict], bool]:
    """Generate a filter for using with dir_db functions to filter series. This
    is expected to operate on series.SeriesInfo objects, so make sure to pass
    Series info as the dir_db transform function.

    :param target: Filter query string, contains all filter requirements

    :return: a partial function that takes a set of test attributes
    """
    filter_func = partial(
        filter_run,
        funcs=SERIES_FUNCS,
        target=target)

    return filter_func
