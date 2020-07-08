"""This module contains everything involved in parsing and evaluating the
results of test runs. This includes the base for the 'result parser' plugins
themselves, as well as functions for performing this parsing. Additionally,
it contains the functions used to get the base result values, as well as
resolving result evaluations."""

import textwrap
from typing import IO, Callable

from pavilion.test_config import resolver
from . import parsers
from .base import base_results, ResultError, BASE_RESULTS
from .evaluations import check_expression, evaluate_results
from .parsers import parse_results, ResultParser, get_plugin


def get_result_logger(log_file: IO[str]) -> Callable[..., None]:
    """Return a result logger function that will write to the given outfile
    and track the indentation level. The logger will take
    the string to log, and an optional lvl argument to change the
    indent level. If the log file is None, this will silently drop all logs."""

    log_tab_level = 0

    def log(msg, lvl=None):
        """Log the given message to the log_file."""

        nonlocal log_tab_level

        if lvl is not None:
            log_tab_level = lvl

        if log_file is not None:
            log_file.write(textwrap.indent(msg, "  " * log_tab_level))
            log_file.write('\n')

    return log


def check_config(parser_conf, evaluate_conf):
    """Make sure the result config is sensible, both for result parsers and
evaluations.

For result parsers we check for:

- Duplicated key names.
- Reserved key names.
- Bad parser plugin arguments.

For evaluations we check for:
- Reserved key names.
- Invalid expression syntax.

:raises TestRunError: When a config breaks the rules.
"""

    # Track the key_names seen, along with the 'per_file' setting for each.
    # Keys still have to be unique, even if they won't collide due to
    # 'per_file'.
    key_names = {key:parsers.PER_FIRST for key in BASE_RESULTS.keys()}
    errors = []

    for rtype in parser_conf:
        for key, rconf in parser_conf[rtype].items():
            action = rconf.get('action')
            per_file = rconf.get('per_file')

            # Don't check args if they have deferred values.
            for values in rconf.values():
                if isinstance(values, dict):
                    values = list(values.values())
                if not isinstance(values, list):
                    values = [values]

                for value in values:
                    if resolver.TestConfigResolver.was_deferred(value):
                        continue

            if key in BASE_RESULTS.keys():
                raise ResultError(
                    "Result parser key '{}' under parser '{}' is reserved."
                    .format(key, rtype)
                )

            if key in key_names:
                raise ResultError(
                    "Duplicate result parser key name '{}' under parser '{}'"
                    .format(key, rtype)
                )

            if (key == 'result'
                    and action not in (parsers.ACTION_TRUE,
                                       parsers.ACTION_FALSE)
                    and per_file not in (parsers.PER_FIRST, parsers.PER_LAST,
                                         parsers.PER_ANY, parsers.PER_ALL)):
                raise ResultError(
                    "Result parser has key 'result', but must store a "
                    "boolean. Use action 'first' or 'last', along with a "
                    "per_file setting of 'first', 'last', 'any', or 'all'")

            key_names[key] = per_file

            parser = get_plugin(rtype)
            try:
                parser.check_args(**rconf)
            except ResultError as err:
                raise ResultError(
                    "Key '{}': {}".format(key, err.args[0]))

        for key, expr in evaluate_conf.items():
            if key in BASE_RESULTS:
                raise ResultError(
                    "Key '{}' in the result evaluate section is reserved."
                    .format(key)
                )

            # Don't check the expression if it is deferred.
            if resolver.TestConfigResolver.was_deferred(expr):
                continue

            check_expression(expr)

    return errors
