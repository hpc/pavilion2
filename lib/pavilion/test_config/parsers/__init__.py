import re

import lark as _lark
from pavilion import output as _output
from .common import ParserValueError
from .expressions import get_expr_parser
from .strings import get_string_parser


class ErrorCat:
    def __init__(self, message, examples, disambiguator=None):
        """
        :param message:
        :param examples:
        :param disambiguator:
        """

        self.message = message
        self.examples = examples
        self.disambiguator = None
        if disambiguator is not None:
            self.disambiguator = re.compile(disambiguator)


BAD_EXAMPLES = [
    ErrorCat('Unmatched "{{"', ['{{ 9', '{{', '[~ {{ ~]']),
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
    #ErrorCat('')
]

a = 1 + + 2


class StringParserError(ValueError):
    """Common error to raise when parsing problems are encountered."""

    def __init__(self, message, context):
        self.message = message
        self.context = context


def parse_text(text, var_man) -> str:
    """
    :param str string:
    :param pavilion.test_config.variables.VariableSetManager var_man:
    :return:
    """

    parser = get_string_parser(var_man)

    try:
        value = parser.parse(text)
    except (_lark.UnexpectedCharacters, _lark.UnexpectedToken) as err:
        # Try to figure out why the error happened based on examples.
        err_type = match_examples(err, parser.parse, BAD_EXAMPLES, text)
        raise StringParserError(err_type, err.get_context(text))
    except ParserValueError as err:
        # These errors are already really specific. We don't have to
        # figure them out.
        raise StringParserError(err.args[0], err.get_context(text))

    return value


def match_examples(exc, parse_fn, examples, text):
    """ Given a parser instance and a dictionary mapping some label with
        some malformed syntax examples, it'll return the label for the
        example that bests matches the current error.
    :param exc:
    :param parse_fn:
    :param list[ErrorCat] examples:
    :param text:
    :return:
    """

    if not hasattr(exc, 'state'):
        return None

    err_pos = exc.pos_in_stream + 1

    err_string = text
    while err_pos <= len(text):
        try:
            parse_fn(text[:err_pos])
        except Exception as err:
            if err.state == exc.state:
                err_string = text[exc.pos_in_stream:err_pos]
                break
        err_pos += 1

    candidate = None
    for example in examples:
        partial_match = False
        for ex_text in example.examples:
            try:
                parse_fn(ex_text)
            except _lark.UnexpectedCharacters as ut:
                if not isinstance(exc, _lark.UnexpectedCharacters):
                    continue

                if ex_text[ut.pos_in_stream] == text[exc.pos_in_stream]:
                    return example.message

            except _lark.UnexpectedToken as ut:
                if not isinstance(exc, _lark.UnexpectedToken):
                    continue

                if ut.state == exc.state:
                    partial_match = True
                    if ut.token == exc.token:
                        # Try exact match first
                        return example.message
            except ParserValueError:
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

    return candidate
