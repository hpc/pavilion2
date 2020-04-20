import lark
import pprint
from typing import Union
from pavilion import functions

STRING_GRAMMAR = r'''

start: string

// It's important that each of these start with a terminal, rather than 
// a reference back to the 'string' rule. A 'STRING' terminal (or nothing) 
// is definite, but a 'string' would be non-deterministic.
string: STRING?
      | STRING? escape string
      | STRING? sub_string string
      | STRING? expr string

sub_string: SUB_STRING_START string "~" separator "]"
SUB_STRING_START: "[~"
escape: ESCAPE

expr: EXPR_START STRING? EXPR_END
EXPR_START: "{{"
EXPR_END: "}}"

separator: STRING? (escape STRING)*

// A string can be empty
// This will match any characters that aren't a '{' '[' or '\\', or
// a '{' as long as it isn't followed by another '{', or
// a '[' as long as it isn't followed by a '~'. 
STRING: /([^{[\\~}]|{(?=[^{])|}(?=[^}])|\[(?=[^~]))+/
ESCAPE: /\\./
'''

EXPR_GRAMMAR = r'''

start: expr
     |          // An empty string is valid 

expr: or_expr

// These set order of operations. 
// See https://en.wikipedia.org/wiki/Operator-precedence_parser
or_expr: and_expr ( "or" and_expr )?          
and_expr: not_expr ( "and" not_expr )?
not_expr: NOT? compare_expr
compare_expr: add_expr ((EQ | NOT_EQ | "<" | ">" | LT_EQ | GT_EQ ) add_expr)*
add_expr: mult_expr ((PLUS | MINUS) mult_expr)*
mult_expr: pow_expr ((TIMES | DIVIDE | INT_DIV | MODULUS) pow_expr)*
pow_expr: primary ("^" primary)?
primary: literal 
       | var_ref 
       | negative
       | "(" expr ")"
       | function_call
//       | list_
//       | ESCAPED_STRING

function_call: NAME "(" (expr ("," expr)*)? ")"

negative: MINUS primary

literal: INTEGER
       | FLOAT
//       | BOOL
       
list_: "[" expr ("," expr)* "," "]"

_STRING_INNER: /.*?/
_STRING_ESC_INNER: _STRING_INNER /(?<!\\)(\\\\)*?/
ESCAPED_STRING : "\"" _STRING_ESC_INNER "\""

PLUS: "+"
MINUS: "-"
TIMES: "*"
DIVIDE: "/"
INT_DIV: "//"
MODULUS: "%"
NOT: "not"
EQ: "=="
NOT_EQ: "!="
LT_EQ: "<="
GT_EQ: ">="
INTEGER: /\d+/
FLOAT: /\d+\.\d+/
BOOL: "True" | "False"

// Variable references are kept generic. We'll use this both
// for Pavilion string variables and result calculation variables.
var_ref: NAME ("." var_key)*
var_key: NAME
        | INTEGER
        | "*"

NAME: /[a-zA-Z][a-zA-Z0-9_]*/

%ignore  / +(?=[^.(])/
'''

_EXPR_PARSER = None
_STRING_PARSER = None

def get_expr_parser(debug=False):
    global _EXPR_PARSER

    if debug or _EXPR_PARSER is None:
        parser = lark.Lark(
            grammar=EXPR_GRAMMAR,
            start='expr',
            transformer=ExprTransformer(),
            parser='lalr',
            debug=debug
        )
    else:
        parser = _EXPR_PARSER

    if not debug and _EXPR_PARSER is None:
        _EXPR_PARSER = parser

    return parser

def get_string_parser(debug=False):
    global _STRING_PARSER

    if debug or _STRING_PARSER is None:
        parser = lark.Lark(
            grammar=STRING_GRAMMAR,
            parser='lalr',
            debug=debug
        )
    else:
        parser = _STRING_PARSER

    if not debug and _STRING_PARSER is None:
        _STRING_PARSER = parser

    return parser


class ParseError(ValueError):
    def __init__(self, token, message):
        super().__init__(message)

        self.token = token


class ExprTransformer(lark.Transformer):
    """Transformer for expressions."""

    # pylint: disable=

    NUM_TYPES = (
        int,
        float,
        bool
    )

    def expr(self, items):
        """Simply pass up the expression result."""

        return items[0]

    def or_expr(self, items):
        """Pass a single item up. Otherwise, apply ``'or'`` logical operations.

        :param list[lark.Token] items: Tokens to logically ``'or``. The
            'or' terminals are not included.
        :return:
        """

        or_items = items.copy()
        acc = or_items.pop().value

        while or_items:
            acc = acc or or_items.pop().value

        return self._merge_tokens(items, acc)

    def and_expr(self, items):
        """Pass a single item up. Otherwise, apply ``'and'`` logical operations.

        :param list[lark.Token] items: Tokens to logically ``'and'``. The
            'and' terminals are not included.
        :return:
        """

        and_items = items.copy()
        acc = and_items.pop().value

        while and_items:
            acc = acc and and_items.pop().value

        return self._merge_tokens(items, acc)

    def not_expr(self, items) -> lark.Token:
        """Apply a logical not, if ``'not'`` is present.

        :param list[lark.Token] items: One or two tokens
        """

        if items[0] == 'not':
            return self._merge_tokens(items, not items[1].value)
        return items[0]

    def compare_expr(self, items) -> lark.Token:
        """Pass a single item up. Otherwise, perform the chain of comparisons.
        Chained comparisons ``'3 < 7 < 10'`` will be evaluated as
        ``'3 < 7 and 7 < 10'``, just like in Python.
        :param list[lark.Token] items: An odd number of tokens. Every second
            token is an comparison operator (``'=='``, ``'!='``, ``'<'``,
            ``'>'``, ``'<='``, ``'>='``).
        """

        comp_items = items.copy()
        comp_items.reverse()
        left = comp_items.pop()
        if not comp_items:
            return left

        acc = True

        while comp_items and acc:
            comparator = comp_items.pop()
            right = comp_items.pop()

            if comparator == '==':
                acc = acc and (left == right)
            elif comparator == '!=':
                acc = acc and (left != right)
            elif comparator == '<':
                acc = acc and (left < right)
            elif comparator == '>':
                acc = acc and (left > right)
            elif comparator == '<=':
                acc = acc and (left <= right)
            elif comparator == '>=':
                acc = acc and (left >= right)

        return self._merge_tokens(items, acc)

    def add_expr(self, items) -> lark.Token:
        """Pass single items up, otherwise, perform the chain of
        addition and subtraction operations. These are valid for numeric
        values only.

        :param list[lark.Token] items: An odd number of tokens. Every second
            token is an operator (``'+'`` or ``'-'``).
        """

        if len(items) > 1:
            for tok in items[0::2]:
                if not isinstance(tok.value, self.NUM_TYPES):
                    raise ParseError(
                        tok,
                        "Non-numeric value used in add/sub operation.")
        elif len(items) == 1:
            return items[0]
        else:
            raise RuntimeError("Add_expr expects at least one token.")

        add_items = items.copy()
        accum = add_items.pop().value
        while add_items:
            op = add_items.pop()
            val = add_items.pop().value
            if op == '+':
                accum += val
            elif op == '-':
                accum -= val
            else:
                raise RuntimeError("Invalid operation '{}' in expression."
                                   .format(op))

        return self._merge_tokens(items, accum)

    def mult_expr(self, items) -> lark.Token:
        """Pass single items up, otherwise, perform the chain of
        multiplication and division operations. These are valid for numeric
        values only.
        :param list[lark.Token] items: An odd number of tokens. Every second
            token is an operator (``'*'``, ``'/'``, ``'//'``, ``'%'``).
        """

        if len(items) > 1:
            for tok in items[0::2]:
                if not isinstance(tok.value, self.NUM_TYPES):
                    raise ParseError(
                        tok,
                        "Non-numeric value used in math operation.")
        elif len(items) == 1:
            return items[0]
        else:
            raise RuntimeError("Mult_expr expects at least one token.")

        mult_items = items.copy()
        mult_items.reverse()

        accum = mult_items.pop().value
        while mult_items:
            op = mult_items.pop()
            val = mult_items.pop().value
            if op.value == '*':
                accum *= val
            elif op.value == '/':
                accum /= val
            elif op.value == '//':
                accum //= val
            elif op.value == '%':
                accum %= val
            else:
                raise RuntimeError("Invalid operation '{}' in expression."
                                   .format(op))

        return self._merge_tokens(items, accum)

    def pow_expr(self, items) -> lark.Token:
        """Pass single items up, otherwise raise the first item to the
        power of the second item.
        :param list[lark.Token] items: One or two tokens
        """

        if len(items) == 2:
            for tok in items:
                if not isinstance(tok.value, self.NUM_TYPES):
                    raise ParseError(
                        tok,
                        "You may only used in power ")

        if len(items) == 2:
            return self._merge_tokens(items, items[0].value ** items[1].value)
        else:
            return items[0]

    def primary(self, items) -> lark.Token:
        """Simply pass the value up to the next layer.
        :param list[Token] items: Will only be a single item.
        """

        # Parenthetical expressions are handled implicitly, since
        # the parenthesis aren't captured as tokens.
        return items[0]

    def negative(self, items) -> lark.Token:
        """
        :param list[lark.Token] items:
        :return:
        """
        val = items[1].value
        if not isinstance(val, self.NUM_TYPES):
            raise ParseError(items[1], "Only numeric values may be made "
                                       "negative.")

        return self._merge_tokens(items, -items[1].value)

    def literal(self, items) -> lark.Token:
        """Just pass up the literal value.
        :param list[lark.Token] items: A single token.
        """

        return items[0]

    def list_(self, items) -> lark.Token:
        """Handle explicit lists.

        :param list[lark.Token] items: The list item tokens.
        """

        return self._merge_tokens(items, [item.value for item in items])

    def var_ref(self, items) -> lark.Token:
        """
        :param items:
        :return:
        """
        var = items[0]
        var.value = ord(var.value[0])

        return var

    def function_call(self, items) -> lark.Token:
        """Look up the function call, and call it with the given argument
        values.

        :param list[lark.Token] items: A function name token and zero or more
            argument tokens.
        """

        func_name = items[0].value
        args = [tok.value for tok in items[1:]]

        try:
            func = functions.get_plugin(func_name)
        except functions.FunctionPluginError:
            raise ParseError(
                token=items[0],
                message="No such function '{}'".format(func_name))

        try:
            result = func(*args)
        except functions.FunctionArgError as err:
            raise ParseError(
                self._merge_tokens(items, None),
                "Invalid arguments: {}".format(err))
        except functions.FunctionPluginError as err:
            # The function plugins give a reasonable message.
            raise ParseError(self._merge_tokens(items, None), err)

        return result

    def INTEGER(self, tok) -> lark.Token:
        """Convert to an int.

        :param lark.Token tok:
        """

        try:
            tok.value = int(tok.value)
        except ValueError:
            raise ParseError(tok, "Invalid integer '{}'".format(tok.value))
        return tok

    def FLOAT(self, tok: lark.Token) -> lark.Token:
        """Convert to a float.

        :param lark.Token tok:
        """
        try:
            tok.value = float(tok.value)
        except ValueError:
            raise RuntimeError("Invalid integer '{}'".format(tok.value))
        return tok

    def BOOL(self, tok: lark.Token) -> lark.Token:
        """Convert to a boolean.
        """

        if tok.value == 'True':
            tok.value = True
        elif tok.value == 'False':
            tok.value = False
        else:
            raise RuntimeError("Invalid boolean value.")

        return tok

    def _merge_tokens(self, tokens, value):
        """asdfasdf

        :param list[lark.Token] tokens:
        :return:
        """
        tokens = tokens.copy()
        tokens.reverse()

        tok = tokens.pop()
        pos_in_stream = tok.pos_in_stream
        line = tok.line
        column = tok.column
        end_line = tok.end_line
        end_column = tok.end_column
        end_pos = tok.end_pos

        while tokens:
            tok = tokens.pop()
            pos_in_stream = min(pos_in_stream, tok.pos_in_stream)
            end_pos = max(end_pos, tok.end_pos)

            if tok.line < line:
                line = tok.line
                column = tok.column
            elif tok.line == line:
                column = tok.column

            if tok.end_line > end_line:
                end_line = tok.end_line
                column = tok.column
            elif tok.end_line == end_line:
                column = tok.column

        return lark.Token(
            type_='<merged>',
            value=value,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            pos_in_stream=pos_in_stream,
            end_pos=end_pos
        )
