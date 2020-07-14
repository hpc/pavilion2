"""This module contains everything involved in parsing and evaluating the
results of test runs. This includes the base for the 'result parser' plugins
themselves, as well as functions for performing this parsing. Additionally,
it contains the functions used to get the base result values, as well as
resolving result evaluations."""

from pavilion.test_config import resolver
from .evaluations import check_expression, evaluate_results, StringParserError
from .base import base_results, ResultError, BASE_RESULTS
from . import parsers
from .parsers import parse_results


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
