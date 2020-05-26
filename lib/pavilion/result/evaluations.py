from typing import Dict, List

from pavilion.test_config.parsers import (check_expression, StringParserError,
                                          parse_evaluation_expression)

from .base import BASE_RESULTS


def check_evaluations(evaluations: Dict[str, str]) -> List[str]:
    """Check all evaluations for basic errors.  Returns a list of
    found errors."""

    errors = []

    for key, expr in evaluations.items():
        if key in BASE_RESULTS:
            errors.append("Key '{}' in result.evaluate section is reserved.")

        error = check_expression(expr)
        if error is not None:
            errors.append(error)

    return errors


def evaluate_results(results: dict, evaluations: Dict[str, str]):
    """Perform result evaluations according to
    :param results:
    :param evaluations:
    :return:
    """

    if 'result' not in evaluations:
        evaluations['result'] = 'return_value == 0'

    for key, expr in evaluations.items():

        try:
            results[key] = parse_evaluation_expression(expr, results)
        except StringParserError as err:
            pass
