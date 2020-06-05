"""Handles performing evaluations on results."""

from typing import Dict, List

from pavilion.test_config.parsers import (check_expression, StringParserError,
                                          parse_evaluation_dict)

from .base import BASE_RESULTS, ResultError


def check_evaluations(evaluations: Dict[str, str]) -> List[str]:
    """Check all evaluations for basic errors.  Returns a list of
    found errors."""

    errors = []

    for key, expr in evaluations.items():
        if key in BASE_RESULTS:
            errors.append("Key '{}' in result.evaluate section is reserved."
                          .format(key))

        error = check_expression(expr)
        if error is not None:
            errors.append(error)

        key_parts = key.split('.')
        if key_parts.count('*') > 1:
            errors.append("Key '{}' in result.evaluate can only contain one "
                          "'*'".format(key))

    return errors


def evaluate_results(results: dict, evaluations: Dict[str, str]):
    """Perform result evaluations using an expression parser. The variables
    in such expressions are pulled from the results data structure, and the
    results are stored there too.
    :param results: The result dict. Will be modified in place.
    :param evaluations: A dictionary of evals to perform.
    :return:
    """

    if 'result' not in evaluations:
        evaluations['result'] = 'return_value == 0'

    try:
        parse_evaluation_dict(evaluations, results)
    except StringParserError as err:
        raise ResultError("\n".join([err.message, err.context]))
    except ValueError as err:
        # There was a reference loop.
        raise ResultError(err.args[0])
