from typing import Dict, List

from pavilion.test_config.parsers import (
    AnalysisExprTransformer, get_expr_parser)

from .base import BASE_RESULTS


def check_analysis(analysis: Dict[str, str]) -> List[str]:
    """Make sure """

    errors = []

    for key, expr in analysis.items():




def analyze_results(results: dict, analysis: Dict[str,str]):
    """Perform result analysis according to
    :param results:
    :param analysis:
    :return:
    """

    parser = get_expr_parser()
    transformer = AnalysisExprTransformer(results)

    if 'result' not in analysis:
        analysis['result'] = 'return_value == 0'

    for key, expr in analysis.items():
        try:
            tree = parser.parse(expr)

            results[key] = transformer.transform(tree)

        except:
            pass

