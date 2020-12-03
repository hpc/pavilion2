"""Handles performing evaluations on results."""

from typing import Dict, Callable

import lark as _lark
from pavilion import utils
from pavilion.test_config.parsers import (check_expression, StringParserError,
                                          get_expr_parser,
                                          EvaluationExprTransformer,
                                          VarRefVisitor, match_examples,
                                          BAD_EXAMPLES, ParserValueError)
from .common import ResultError
from .base import BASE_RESULTS


def check_evaluations(evaluations: Dict[str, str]):
    """Check all evaluations for basic errors.

    :raises ResultError: For detected problems.
    """

    for key, expr in evaluations.items():
        if key in BASE_RESULTS:
            raise ResultError(
                "Key '{}' in result.evaluate section is reserved."
                .format(key))

        try:
            check_expression(expr)
        except StringParserError as err:
            raise ResultError(
                "Error parsing evaluate expression for key '{}':\n{}\n{}"
                .format(key, err.message, err.context)
            )


def evaluate_results(results: dict, evaluations: Dict[str, str],
                     log: utils.IndentedLog):
    """Perform result evaluations using an expression parser. The variables
    in such expressions are pulled from the results data structure, and the
    results are stored there too.
    :param results: The result dict. Will be modified in place.
    :param evaluations: A dictionary of evals to perform.
    :param log: The optional logger function from (result.get_result_logger)
    :return:
    """

    if log is None:
        def log(*_, **__):
            """Drop any log lines."""

    log.indent = 0
    log("Evaluating result evaluations.")

    if 'result' not in results and 'result' not in evaluations:
        evaluations['result'] = 'return_value == 0'

    try:
        parse_evaluation_dict(evaluations, results, log)
    except StringParserError as err:
        raise ResultError("\n".join([err.message, err.context]))
    except ValueError as err:
        # There was a reference loop.
        raise ResultError(err.args[0])


def parse_evaluation_dict(eval_dict: Dict[str, str], results: dict,
                          log: Callable[..., None]) -> None:
    """Parse the dictionary of evaluation expressions, given that some of them
    may contain references to each other. Each evaluated value will be stored
    under its corresponding key in the results dict.

    :raises StringParserError: When there's an error parsing or resolving
        one of the expressions. The error will already contain key information.
    :raises ValueError: When there's a reference loop.
    """

    parser = get_expr_parser()
    transformer = EvaluationExprTransformer(results)
    var_ref_visitor = VarRefVisitor()

    unresolved = {}

    log.indent = 1
    for key, expr in eval_dict.items():
        log("Parsing the evaluate expression '{}'".format(expr))
        try:
            tree = parser.parse(expr)
        except (_lark.UnexpectedCharacters, _lark.UnexpectedToken) as err:
            # Try to figure out why the error happened based on examples.
            err_type = match_examples(err, parser.parse, BAD_EXAMPLES, expr)
            log("Error parsing expression, failing.")
            log(err_type)
            log(err.get_context(expr))
            raise StringParserError(
                "Error evaluating expression '{}' for key '{}':\n{}"
                .format(expr, key, err_type), err.get_context(expr))

        var_refs = var_ref_visitor.visit(tree)

        unresolved[key] = (tree, var_refs, expr)

    log.indent = 0
    log("Resolving evaluations.")
    log.indent = 1

    while unresolved:
        resolved = []
        for key, (tree, var_refs, expr) in unresolved.items():
            for var in var_refs:
                if var in unresolved:
                    break
            else:
                log("Resolving evaluation '{}': '{}'".format(key, expr))
                try:
                    results[key] = transformer.transform(tree)
                except ParserValueError as err:
                    log("Error resolving evaluation: {}".format(err.args[0]))
                    log(err.get_context(expr))

                    # Any value errors should be converted to this error type.
                    raise StringParserError(err.args[0], err.get_context(expr))
                resolved.append(key)
                log.indent = 2
                log("Value resolved to: '{}'".format(results[key]))

        if not resolved:
            # Pass up the unresolved
            raise ValueError("Reference loops found amongst evaluation keys "
                             "{}.".format(tuple(unresolved.keys())))

        for key in resolved:
            del unresolved[key]

    log.indent = 0
    log("Finished resolving expressions")
