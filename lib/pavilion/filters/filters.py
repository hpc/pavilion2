"""This module contains functions to generate filter functions for handing
to dir_db commands."""

# pylint: disable=invalid-name

import argparse
import datetime as dt
import fnmatch
import re
from functools import partial
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Callable, List, Union

from pavilion import series
from pavilion import utils
from pavilion.status_file import TestStatusFile, SeriesStatusFile, StatusError, \
    STATES, SERIES_STATES
from pavilion import sys_vars
from pavilion.test_run import TestRun
from pavilion import variables

from lark import Lark

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

# used to index functions and their valid operators in filter queries
FUNC = 0
OPS  = 1

# accepted operators in filter queries
OP_EQ  = '='
OP_NEQ = '!='
OP_LT  = '<'
OP_GT  = '>'
OP_OR  = '|'
OP_AND = ' '
OP_NOT = '!'

OP_FUNCS = {
    OP_EQ = lambda x, y: x == y,
    OP_NEQ = lambda x, y: x != y,
    OP_LT = lambda x, y: x < y,
    OP_GT = lambda x, y: x > y,
    OP_OR = lambda x, y: x or y,
    OP_AND = lambda x, y: x and y,
    OP_NOT = lambda x: not x
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
            "  has_state=STATE    Include only {} who have had the \n"
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
            "  nodes=NODES        Include only {} that match NODES. Wildcards and ranges defined \n"
            "                       by brackets (i.e., node[001-005]) are allowed. \n"
            "  num_nodes>NUM_NODES \n"
            "                     Include only {} that have greater or less than NUM_NODES. \n"
            "                       Comparators <, >, and = are accepted. \n"
            "  STATE              Include only {} whose most recent state is the one given. \n"
            "                       States can be listed with 'pav show states' \n"
            "  sys_name=SYS_NAME  Include only {} that match the given system name, as \n"
            "                       presented by the sys.sys_name pavilion variable. \n"
            "  user=USER          Include only {} started by this user. \n")

filter_parser = Lark.open("filters.lark")

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

def complete(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "complete" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "complete" attribute
    """
    return attrs.get('complete', False)

def name(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "name" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "name" attribute
    """
    name_parse = re.compile(r'^([a-zA-Z0-9_*?\[\]-]+)'  # The test suite name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?'  # The test name.
                            r'(?:\.([a-zA-Z0-9_*?\[\]-]+?))?$'  # The permutation name.
                            )
    test_name = attrs.get('name') or ''
    filter_match = name_parse.match(val)
    name_match = name_parse.match(test_name)

    suite = '*'
    test = '*'
    perm = '*'

    if filter_match is not None:
        suite, test, perm = filter_match.groups()

    if name_match is not None:
        _, _, test_perm = name_match.groups()

        # allows permutation glob filters to match tests without permutations
        # e.g., name=suite.test.* will match suite.test
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

def user(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "user" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "user" attribute
    """
    return attrs.get('user', False) == val

def sys_name(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "sys_name" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "sys_name" attribute
    """

    return attrs.get('sys_name', False) == val

def passed(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "passed" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "passed" attribute
    """
    return attrs.get('result', False) == TestRun.PASS

def failed(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "failed" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "failed" attribute
    """
    return attrs.get('result', False) == TestRun.FAIL

def result_error(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "result_error" status of a test

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "result_error" attribute
    """
    return attrs.get('result', False) == TestRun.ERROR

def created(attrs: Union[Dict, series.SeriesInfo], operator: str, val: str) -> bool:
    """Return whether 'created' status of a test is greater or less than a given time

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query
    :param val: the value of the filter query

    :return: result of the test or series 'created' before or after a given time
    """

    time_val = utils.hr_cutoff_to_ts(val, dt.datetime.now())

    if attrs.get('created') is None:
        return False

    if operator == OP_GT:
        return attrs.get('created') < time_val
    elif operator == OP_LT:
        return attrs.get('created') > time_val
    else:
        raise ValueError(
                    "Operator {} not recognized.".format(operator))

def partition(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    """Return "partition" status

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "partition" attribute
    """
    return attrs.get('partition', False) == val

def nodes(attrs: Union[Dict, series.SeriesInfo], val: str):
    """Return "partition" status

    :param attrs: attributes of a given test or series
    :param val: the value of the filter query

    :return: result of the test or series "partition" attribute
    """
    if 'results' in attrs and 'sched' in attrs['results']:
        if 'test_node_list' not in attrs['results']['sched']:
            node_var = variables.VariableSetManager.load(Path(attrs.get('path')) / 'variables')

            if 'sched' in node_var.as_dict() and 'test_node_list' in node_var.as_dict()['sched']:
                attrs['results']['sched']['test_node_list'] \
                    = node_var.as_dict()['sched']['test_node_list']

            else:
                return False

        for node in attrs['results']['sched']['test_node_list']:
            if not fnmatch.fnmatch(node, val):
                return False

            return True
    else:
        return False

def all_finished(attrs: Union[Dict, series.SeriesInfo], val: str) -> bool:
    return True

def num_nodes(attrs: Union[Dict, series.SeriesInfo], operator: str, val: str) -> bool:
    """Return whether 'num_nodes' status of a test is greater or less than a given number

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query
    :param val: the value of the filter query

    :return: result of the test or series 'num_nodes' greater or less than a given number
    """
    if 'results' in attrs and 'sched' in attrs['results']:
        if 'test_nodes' in attrs['results']['sched']:
            try:
                int_val = int(val)
            except ValueError:
                return False

            test_nodes = int(attrs['results']['sched']['test_nodes'])

            if operator == OP_GT:
                return test_nodes > int_val
            elif operator == OP_LT:
                return test_nodes < int_val
            elif operator == OP_EQ:
                return test_nodes == int_val
            else:
                raise ValueError(
                            "Operator {} not recognized.".format(operator))


def finished(attrs: Union[Dict, series.SeriesInfo], operator: str, val: str) -> bool:
    """Return whether 'finished' status of a test is greater or less than a given time

    :param attrs: attributes of a given test or series
    :param op: the operator of the filter query
    :param val: the value of the filter query

    :return: result of the test or series 'finished' before or after a given time
    """

    time_val = utils.hr_cutoff_to_ts(val, dt.datetime.now())

    if attrs.get('finished') is None:
        return False

    if operator == OP_GT:
        return attrs.get('finished', False) < time_val
    elif operator == OP_LT:
        return attrs.get('finished', False) > time_val
    else:
        raise ValueError(
                    "Operator {} not recognized.".format(operator))

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

FILTER_FUNCS = {
    'created': created,
    'finished': finished,
    'num_nodes': num_nodes
}

SERIES_FUNCS = {
    'complete': [complete, ''],
    'name': [name, ('=', '!=')],
    'user': [user, ('=', '!=')],
    'sys_name': [sys_name, ('=', '!=')],
    'partition': [partition, ('=')],
    'nodes': [nodes, ('=')],
    'all_started': [all_started, ()]
}

TEST_FUNCS = {
    'complete': [complete, ''],
    'name': [name, ('=', '!=')],
    'user': [user, ('=', '!=')],
    'sys_name': [sys_name, ('=', '!=')],
    'partition': [partition, ('=')],
    'nodes': [nodes, ('=')],
    'result_error': [result_error, ''],
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
    if OP_NEQ in op:
        op = op.replace('!=', '=')
        print(op)
        return not filter_run(attrs, funcs, op)

    return not filter_run(attrs, funcs, op.strip(OP_NOT))

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

def remove_extra_spaces(target: str) -> str:
    """Remove excess spaces from the target

    :param target: filter query string

    :return: the whitespace-trimmed query
    """
    new_target = re.sub(r' *([|!=<>]) *', r'\1', target).strip(' ')

    if FINISHED in new_target or CREATED in new_target:
        new_target = re.sub(r'(created[<>]|finished[<>])'
                            r'(\d+(?:\.\d+)?)\s*'
                            r'(second|minute|hour|day|week|year([s])?)', r'\1\2\3', new_target)
        new_target = re.sub(r'(created[<>]|finished[<>])'
                            r'(\d{4})'
                            r'(-\d{1,2})?'
                            r'(-\d{1,2})?'
                            r'(?:[T ](\d{1,2}))?'
                            r'(:\d{1,2})?'
                            r'(:\d{1,2})?(?:\.\d+)?', r'\1\2\3\4T\5\6\7', new_target)

    return new_target

@dataclass
class QueryNode:
    operator: Optional[Callable] = None
    values: Tuple = ()

def parse_target(target: str, filter_funcs: Dict) -> FilterQuery:
    """Parse the key, operand, and value apart. If there is not an
       operand or value, return the target

    :param target: filter query keyword argument

    :return: the key, operand, and value if applicable, otherwise the target
    """
    if target is None:
        return FilterQuery(operator=lambda _: True)

    target = remove_extra_spaces(target)

    if target == '':
        return QueryNode(operator=lambda _: True)

    if target in SERIES_STATES:
        return QueryNode(operator=lambda x: x[target])

    if target in FILTER_FUNCS:
        return QueryNode(operator=FILTER_FUNCS.get(target))

    for op in [OP_AND, OP_OR]:
        if op in target:
            return QueryNode(
                operator=OP_FUNCS[OP_AND],
                values=tuple(map(lambda x: parse_target(x, filter_funcs), target.split(op, 1)))
            )

    if target.startswith(HAS_STATE + OP_EQ):
        target = target.removeprefix(HAS_STATE + OP_EQ)

        return QueryNode(
            operator=lambda x: has_state(x, target)
        )

    for op in [OP_NEQ, OP_EQ, OP_LT, OP_GT, OP_NOT]:
        if op in target:
            return QueryNode(
                operator=OP_FUNCS[OP_AND],
                values=tuple(map(lambda x: parse_target(x, filter_funcs), target.split(op, 1)))
            )


    return QueryNode()

def filter_run(test_attrs: Union[Dict, series.SeriesInfo], filter_funcs: Dict, target: str) -> bool:
    """Main logic of the filter. Evaluate arguments and apply any operations to them.

    :param test_attrs: attributes of a given test or series
    :param filter_funcs: respective functions for tests or series
    :param target: filter query string

    :return: whether a particular test passes the filter query requirements
    """

    query = parse_target(target, filter_funcs)

    if key.upper() in STATES.list() and filter_funcs == TEST_FUNCS:
        return state(test_attrs, STATE, key, TestStatusFile)

    elif key in SERIES_STATES.list() and filter_funcs == SERIES_FUNCS:
        return state(test_attrs, STATE, key, SeriesStatusFile)

    elif key == HAS_STATE and filter_funcs == TEST_FUNCS:
        return state(test_attrs, HAS_STATE, val, TestStatusFile)

    elif key == HAS_STATE and filter_funcs == SERIES_FUNCS:
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
        filter_funcs=TEST_FUNCS,
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
        filter_funcs=SERIES_FUNCS,
        target=target)

    return filter_func
