from typing import Dict, List

from pavilion.test_config.parsers import (check_expression, StringParserError,
                                          parse_analysis_expression)

from .base import BASE_RESULTS


def check_analysis(analysis: Dict[str, str]) -> List[str]:
    """Check all analysis expressions for basic errors.  Returns a list of
    found errors."""

    errors = []

    for key, expr in analysis.items():
        if key in BASE_RESULTS:
            errors.append("Key '{}' in result.analysis section is reserved.")

        error = check_expression(expr)
        if error is not None:
            errors.append(error)

    return errors


def analyze_results(results: dict, analysis: Dict[str,str]):
    """Perform result analysis according to
    :param results:
    :param analysis:
    :return:
    """

    if 'result' not in analysis:
        analysis['result'] = 'return_value == 0'

    for key, expr in analysis.items():

        try:
            results[key] = parse_analysis_expression(expr, results)
        except StringParserError as err:
            pass

