"""This module contains everything involved in parsing and evaluating the
results of test runs. This includes the base for the 'result parser' plugins
themselves, as well as functions for performing this parsing. Additionally,
it contains the functions used to get the base result values, as well as
resolving result evaluations."""

from pavilion.test_config import resolver
from .evaluations import check_expression, evaluate_results
from .base import base_results, ResultError, BASE_RESULTS
from .parsers import parse_results, ResultParser, get_plugin


def check_config(result_configs):
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

    parser_conf = result_configs['parse']
    evaluate_conf = result_configs['evaluate']

    key_names = []

    print('parser conf', parser_conf)

    for rtype in parser_conf:
        print('rtype', rtype)
        for rconf in parser_conf[rtype]:
            key = rconf.get('key')

            print(key, key in key_names, key_names)

            # Don't check args if they have deferred values.
            for values in rconf.values():
                if isinstance(values, dict):
                    values = list(values.values())
                if not isinstance(values, list):
                    values = [values]

                for value in values:
                    if resolver.TestConfigResolver.was_deferred(value):
                        continue

            if key is None:
                raise RuntimeError(
                    "ResultParser config for parser '{}' missing the 'key' "
                    "attribute. This should be required by the test config, "
                    "but could be broken by a bad plugin."
                    .format(rtype)
                )

            if key in key_names:
                raise ResultError(
                    "Duplicate result parser key name '{}' under parser '{}'"
                    .format(key, rtype)
                )

            if key in BASE_RESULTS.keys() or key == 'result':
                raise ResultError(
                    "Result parser key '{}' under parser '{}' is reserved."
                    .format(key, rtype)
                )

            key_names.append(key)

            parser = get_plugin(rtype)
            parser.check_args(**rconf)

        errors = []

        for key, expr in evaluate_conf.items():
            if key in BASE_RESULTS:
                raise ResultError(
                    "Key '{}' in the result evaluate section is reserved."
                    .format(key)
                )

            # Don't check the expression if it is deferred.
            if resolver.TestConfigResolver.was_deferred(expr):
                continue

            error = check_expression(expr)
            if error is not None:
                raise ResultError(
                    "The result evaluate expression for key '{}' has a syntax "
                    "error:\n{}"
                    .format(key, error))

        return errors
