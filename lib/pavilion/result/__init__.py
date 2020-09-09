"""This module contains everything involved in parsing and evaluating the
results of test runs. This includes the base for the 'result parser' plugins
themselves, as well as functions for performing this parsing. Additionally,
it contains the functions used to get the base result values, as well as
resolving result evaluations."""

import json
import textwrap
from pathlib import Path
from typing import IO, Callable, List

from pavilion import lockfile as _lockfile
from pavilion.test_config import resolver
from . import parsers
from .base import base_results, ResultError, BASE_RESULTS
from .evaluations import check_expression, evaluate_results, StringParserError
from .parsers import parse_results, ResultParser


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
    key_names = set([])
    errors = []

    for rtype in parser_conf:

        defaults = parser_conf[rtype].get('_defaults', {})

        for key, rconf in parser_conf[rtype].items():

            # Don't process this as a normal result parser
            if key == parsers.DEFAULT_KEY:
                continue

            if key in BASE_RESULTS.keys():
                raise ResultError(
                    "Result parser key '{}' under parser '{}' is reserved."
                    .format(key, rtype)
                )

            if key in key_names:
                raise ResultError(
                    "Duplicate result parser key name '{}' under parser '{}'"
                    .format(key, rtype))

            key_names.add(key)
            parser = parsers.get_plugin(rtype)

            rconf = parsers.set_parser_defaults(rconf, defaults)
            parsers.check_parser_conf(rconf, key, parser)

    for key, expr in evaluate_conf.items():
        if key in BASE_RESULTS:
            raise ResultError(
                "Key '{}' in the result evaluate section is reserved."
                .format(key)
            )

        # Don't check the expression if it is deferred.
        if resolver.TestConfigResolver.was_deferred(expr):
            continue

        try:
            check_expression(expr)
        except StringParserError as err:
            raise ResultError(
                "Error parsing result evaluate expression for key '{}': {}\n"
                "{}\n{}"
                .format(key, expr, err.message, err.context)
            )

    return errors


def prune_result_log(log_path: Path, ids: List[str]) -> List[dict]:
    """Remove records corresponding to the given test ids. Ids can be either
    an test run id or a test run uuid.

    :param log_path: The result log path.
    :param ids: A list of test run ids and/or uuids.
    :returns: A list of the pruned result dictionaries.
    :raises ResultError: When we can't overwrite the log file.
    """

    pruned = []
    rewrite_log_path = log_path.with_suffix('.rewrite')
    lockfile_path = log_path.with_suffix(log_path.suffix + '.lock')

    with _lockfile.LockFile(lockfile_path), \
         log_path.open() as result_log, \
            rewrite_log_path.open('w') as rewrite_log:

        for line in result_log:
            try:
                result = json.loads(line)
            except json.JSONDecodeError:
                # If we can't parse the line, just rewrite it as is.
                rewrite_log.write(line)
                continue

            if not (str(result.get('id')) in ids
                    or result.get('uuid') in ids):
                rewrite_log.write(line)
            else:
                pruned.append(result)

        log_path.unlink()
        rewrite_log_path.rename(log_path)

    return pruned
