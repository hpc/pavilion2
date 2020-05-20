from pavilion.test_config import resolver
from .analysis import check_expression, analyze_results
from .base import base_results, ResultError, BASE_RESULTS
from .parsers import parse_results, ResultParser, get_plugin


def check_config(result_configs):
    """Make sure the result config is sensible, both for result parsers and
    analysis bits.

For result parsers we check for:

- Duplicated key names.
- Reserved key names.
- Bad parser plugin arguments.

For analysis we check for:
- Reserved key names.
- Invalid expression syntax.

:raises TestRunError: When a config breaks the rules.
"""

    parser_conf = result_configs['parsers']
    analysis_conf = result_configs['analysis']

    key_names = []

    for rtype in parser_conf:
        for rconf in parser_conf[rtype]:
            key = rconf.get('key')

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

            if key in BASE_RESULTS.keys():
                raise ResultError(
                    "Result parser key '{}' under parser '{}' is reserved."
                    .format(key, rtype)
                )

            key_names.append(key)

            parser = get_plugin(rtype)
            parser.check_args(**rconf)

        errors = []

        for key, expr in analysis_conf.items():
            if key in BASE_RESULTS:
                raise ResultError(
                    "Key '{}' in the result analysis section is reserved."
                    .format(key)
                )

            # Don't check the expression if it is deferred.
            if resolver.TestConfigResolver.was_deferred(expr):
                continue

            error = check_expression(expr)
            if error is not None:
                raise ResultError(
                    "The result analysis expression for key '{}' has a syntax "
                    "error:\n{}"
                    .format(key, error))

        return errors
