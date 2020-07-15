"""Pavilion uses several LALR parsers to interpret the value strings in test
configs.

For most of these values the Pavilion StringParser is applied.

1. Pavilion unique escapes are handled (like ``\\{``).
2. Expressions (text in ``{{<expr>}}`` blocks) are pulled out and parsed
   and resolved by the Expression Parser.
3. Iterations are applied (text in ``[~ {{repeat}} ~]``). The contents of
   these are repeated for all permutations of the contained variables.

If you need to parse an individual Pavilion value string, use the parse_text()
function defined in this module.

The exception to this is result evaluation strings, which are interpreted
directly as a ResultExpression.
"""

import re
from typing import List

import lark as _lark
from .common import ParserValueError
from .expressions import (get_expr_parser, EvaluationExprTransformer,
                          VarRefVisitor)
from .strings import get_string_parser, StringTransformer


class ErrorCat:
    """Instances of this class are used to categorize syntax errors."""
    def __init__(self, message, examples, disambiguator=None):
        """
        :param message: The message to give the user about the error.
        :param examples: Examples to parse match against a given error.
        :param disambiguator: If a match isn't exact (the state matches,
            but not the token), check the string against this regex to
            verify the match.
        """

        self.message = message
        self.examples = examples
        self.disambiguator = None
        if disambiguator is not None:
            self.disambiguator = re.compile(disambiguator)


BAD_EXAMPLES = [
    ErrorCat('Unmatched "{{"', ['{{ 9', '{{', '[~ {{ ~]', 'a {{b }']),
    ErrorCat('Unmatched "[~"', ['[~ hello', '[~']),
    ErrorCat('Nested Expression', ['{{ foo {{ bar }} }}']),
    ErrorCat('Unmatched "}}"', ['baz }}', '}}', '[~ hello }} ~]']),
    ErrorCat('Unescaped tilde', ['~unescaped tilde'],
             disambiguator=r'(?<!\[\\)~'),
    ErrorCat('Trailing Backslash', ['trailing backslash\\'],
             disambiguator=r'(^|[^\\])(\\\\)*\\$'),
    ErrorCat('Unmatched "~<sep>]"', ['hello ~_]', '~_]', '[~a~] ~]']),
    ErrorCat('Nested Iteration', ['[~ foo [~ bar ~] ~]']),
    ErrorCat('Invalid Syntax', ['{{a**b}}', '{{a^^b}}', '{{a== ==b}}',
                                '{{a///b}}', '{{a or or b}}',
                                '{{a+*b}}', '{{1 2}}', '{{"a" 2}}',
                                '{{[1] 2}}', '{{False 2}}']),
    ErrorCat('Hanging Operation', ['{{a+}}', '{{a*}}', '{{a^}}', '{{a<}}',
                                   '{{a or}}', '{{a and}}', '{{not}}']),
    ErrorCat('Unmatched "("', ['{{(a+b}}', '{{funky(}}', '{{funky(a}}']),
    ErrorCat('Unclosed String', ['{{a + "hell}}']),
    ErrorCat('Unclosed List', ['{{a + [1, 2}}', '{{a + [1,}}']),
    ErrorCat('Misplaced Comma', ['{{a + [,1,2,]}}',
                                 '{{a + [1,2,,]}}']),
    ErrorCat('Missing Close Parenthesis',
             ['hello(1, "world"',
              'hello(1, 12',
              'hello(1, 12.3']),
]


class StringParserError(ValueError):
    """Common error to raise when parsing problems are encountered."""

    def __init__(self, message, context):
        self.message = message
        self.context = context

        super().__init__()

    def __str__(self):
        return "\n".join([self.message, self.context])


_TREE_CACHE = {}


def parse_text(text, var_man) -> str:
    """Parse the given text and return the parsed result. Will try to figure
    out, to the best of its ability, exactly what caused any errors and report
    that as part of the StringParser error.

    :param str text: The text to parse.
    :param pavilion.test_config.variables.VariableSetManager var_man:
    :raises variables.DeferredError: When a deferred variable is used.
    :raises StringParserError: For syntax and other errors.
    """

    parser = get_string_parser()
    transformer = StringTransformer(var_man)

    def parse_fn(txt):
        """Shorthand for parsing text."""

        tree = _TREE_CACHE.get(txt)
        if tree is None:
            tree = parser.parse(txt)
            _TREE_CACHE[txt] = tree

        return transformer.transform(tree)

    try:
        # On the surface it may seem that parsing and transforming should be
        # separate steps with their own errors, but expressions are parsed
        # as part of the transformation and may raise their own parse errors.
        value = parse_fn(text)
    except (_lark.UnexpectedCharacters, _lark.UnexpectedToken) as err:
        # Try to figure out why the error happened based on examples.
        err_type = match_examples(err, parse_fn, BAD_EXAMPLES, text)
        raise StringParserError(err_type, err.get_context(text))
    except ParserValueError as err:
        # These errors are already really specific. We don't have to
        # figure them out.
        raise StringParserError(err.args[0], err.get_context(text))

    return value


def check_expression(expr: str) -> List[str]:
    """Check that expr is valid, returning the variables used.

    :raises StringParserError: When the expression can't be parsed.
    """

    parser = get_expr_parser()

    try:
        tree = parser.parse(expr)
    except (_lark.UnexpectedCharacters, _lark.UnexpectedToken) as err:
        # Try to figure out why the error happened based on examples.
        err_type = match_examples(err, parser.parse, BAD_EXAMPLES, expr)
        raise StringParserError(
            "{}:\n{}".format(err_type, err.get_context(expr)),
            err.get_context(expr))

    visitor = VarRefVisitor()
    vars_used = visitor.visit(tree)

    return vars_used


def match_examples(exc, parse_fn, examples, text):
    """Given a parser instance and a dictionary mapping some label with
        some malformed syntax examples, it'll return the label for the
        example that bests matches the current error.

    :param Union[_lark.UnexpectedCharacters,_lark.UnexpectedToken] exc:
    :param parse_fn:
    :param list[ErrorCat] examples:
    :param text:
    :return:
    """

    word_re = re.compile(r'\w+')
    ws_re = re.compile(r'\s+')

    if not hasattr(exc, 'state'):
        return None

    err_pos = exc.pos_in_stream + 1

    # Try to find the smallest subset of text that produces the error.
    err_string = text
    while err_pos <= len(text):
        try:
            parse_fn(text[:err_pos])
        except (_lark.UnexpectedCharacters, _lark.UnexpectedToken) as err:
            if err.state == exc.state:
                err_string = text[exc.pos_in_stream:err_pos]
                break
        err_pos += 1

    # Find an example error that fails at the same parser state.
    candidate = None
    for example in examples:
        partial_match = False
        for ex_text in example.examples:
            try:
                parse_fn(ex_text)
            except _lark.UnexpectedCharacters as err:
                if not isinstance(exc, _lark.UnexpectedCharacters):
                    continue

                # Both the example and the original error got unexpected
                # characters in the stream. If the unexpected characters
                # are roughly the same, call it an exact match.
                if (ex_text[err.pos_in_stream] == text[exc.pos_in_stream] or
                        # Call it exact if they're both alpha-numeric
                        re_compare(ex_text[err.pos_in_stream:],
                                   text[exc.pos_in_stream], word_re) or
                        # Or both whitespace
                        re_compare(ex_text[err.pos_in_stream:],
                                   text[exc.pos_in_stream], ws_re)):
                    return example.message

            except _lark.UnexpectedToken as err:
                if not isinstance(exc, _lark.UnexpectedToken):
                    continue

                # For token errors, check that the state and next token match
                # If just the state matches, we'll call it a partial match
                # and look for something better.
                if err.state == exc.state:
                    partial_match = True
                    if err.token == exc.token:
                        # Try exact match first
                        return example.message
            except ParserValueError:
                # Examples should only raise Token or UnexpectedChar errors.
                # ParserValue errors already come with a useful message.
                raise RuntimeError(
                    "Invalid failure example in string_parsers: '{}'"
                    .format(ex_text))

        if partial_match:
            if not candidate:
                candidate = example.message

            # Check the disambiguator regex.
            if (example.disambiguator is not None and
                    example.disambiguator.search(err_string)):
                return example.message

    if candidate is None:
        candidate = 'Unknown syntax error. Please report at ' \
                    'https://github.com/hpc/pavilion2/issues'

    return candidate


def re_compare(str1: str, str2: str, regex) -> bool:
    """Return True if both strings match the given regex."""

    return regex.match(str1) is not None and regex.match(str2) is not None
