from .common import ParseError
from .expressions import EXPR_GRAMMAR as _EXPR_GRAMMAR
from .expressions import ExprTransformer as _ExprTransformer
from .strings import STRING_GRAMMAR as _STRING_GRAMMAR
from .strings import StringTransformer as _StringTransformer
import lark

_EXPR_PARSER = None
_STRING_PARSER = None


def get_expr_parser(debug=False):

    global _EXPR_PARSER

    if debug or _EXPR_PARSER is None:
        parser = lark.Lark(
            grammar=_EXPR_GRAMMAR,
            parser='lalr',
            debug=debug
        )
    else:
        parser = _EXPR_PARSER

    if not debug and _EXPR_PARSER is None:
        _EXPR_PARSER = parser

    return parser


def get_string_parser(var_man, debug=False):
    global _STRING_PARSER

    if debug or _STRING_PARSER is None:
        parser = lark.Lark(
            grammar=_STRING_GRAMMAR,
            transformer=_StringTransformer(var_man),
            parser='lalr',
            debug=debug
        )
    else:
        parser = _STRING_PARSER

    if not debug and _STRING_PARSER is None:
        _STRING_PARSER = parser

    return parser
