"""Grammar and transformer for Pavilion expression syntax."""

import lark
import ast
from pavilion import functions
from .common import PavTransformer, ParserValueError


EXPR_GRAMMAR = r'''

start: expr _WS?
     |          // An empty string is valid 
_WS: /\s+/

expr: or_expr

// These set order of operations. 
// See https://en.wikipedia.org/wiki/Operator-precedence_parser
or_expr: and_expr ( "or" and_expr )?          
and_expr: not_expr ( "and" not_expr )?
not_expr: NOT? compare_expr
compare_expr: add_expr ((EQ | NOT_EQ | LT | GT | LT_EQ | GT_EQ ) add_expr)*
add_expr: mult_expr ((PLUS | MINUS) mult_expr)*
mult_expr: pow_expr ((TIMES | DIVIDE | INT_DIV | MODULUS) pow_expr)*
pow_expr: primary ("^" primary)?
primary: literal 
       | var_ref 
       | negative
       | "(" expr ")"
       | function_call
       | list_
       | ESCAPED_STRING

function_call: NAME "(" (expr ("," expr)*)? ")"

negative: (MINUS|PLUS) primary

literal: INTEGER
       | FLOAT
       | BOOL
       
list_: L_BRACKET (expr ("," expr)* ","?)? R_BRACKET

// Variable references are kept generic. We'll use this both
// for Pavilion string variables and result calculation variables.
var_ref: NAME ("." var_key)*
var_key: NAME
        | INTEGER
        | TIMES

_STRING_INNER: /.*?/
_STRING_ESC_INNER: _STRING_INNER /(?<!\\)(\\\\)*?/
ESCAPED_STRING : "\"" _STRING_ESC_INNER "\""

L_BRACKET: "["
R_BRACKET: "]"
PLUS: "+"
MINUS: "-"
TIMES: "*"
DIVIDE: "/"
INT_DIV: "//"
MODULUS: "%"
NOT: "not"
EQ: "=="
NOT_EQ: "!="
LT: "<"
GT: ">"
LT_EQ: "<="
GT_EQ: ">="
INTEGER: /\d+/
FLOAT: /\d+\.\d+/
// This will be prioritized over 'NAME' matches
BOOL.2: "True" | "False"

NAME.1: /[a-zA-Z][a-zA-Z0-9_]*/

%ignore  / +(?=[^.(])/
'''

_EXPR_PARSER = None


def get_expr_parser(debug=False):
    """Return an expression parser (cached if possible)."""

    global _EXPR_PARSER

    if debug or _EXPR_PARSER is None:
        parser = lark.Lark(
            grammar=EXPR_GRAMMAR,
            parser='lalr',
            debug=debug
        )
    else:
        parser = _EXPR_PARSER

    if not debug and _EXPR_PARSER is None:
        _EXPR_PARSER = parser

    return parser


class ExprTransformer(PavTransformer):
    """Transforms the expression parse tree into an actual value."""

    # pylint: disable=

    NUM_TYPES = (
        int,
        float,
        bool
    )

    def start(self, items):
        """Returns the final value of the expression."""

        if not items:
            return ''

        print(items)
        return items[0].value

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
            acc = or_items.pop().value or acc

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
            acc = and_items.pop().value and acc

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

        if len(items) == 1:
            return items[0]

        comp_items = items.copy()
        comp_items.reverse()
        left = comp_items.pop().value

        acc = True

        while comp_items and acc:
            comparator = comp_items.pop()
            right = comp_items.pop().value

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
            else:
                raise RuntimeError("Invalid comparator '{}'".format(comparator))

            left = right

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
                    raise ParserValueError(
                        tok,
                        "Non-numeric value in math operation")
        elif len(items) == 1:
            return items[0]
        else:
            raise RuntimeError("Add_expr expects at least one token.")

        add_items = items.copy()
        add_items.reverse()
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
                    raise ParserValueError(
                        tok,
                        "Non-numeric value in math operation")
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
                    raise ParserValueError(
                        tok,
                        "Non-numeric value in math operation")

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
            raise ParserValueError(
                items[1],
                "Non-numeric value in math operation")

        value = items[1].value
        if items[0].value == '-':
            value = -value

        return self._merge_tokens(items, value)

    def literal(self, items) -> lark.Token:
        """Just pass up the literal value.
        :param list[lark.Token] items: A single token.
        """

        return items[0]

    def list_(self, items) -> lark.Token:
        """Handle explicit lists.

        :param list[lark.Token] items: The list item tokens.
        """

        return self._merge_tokens(items, [item.value for item in items[1:-1]])

    def var_ref(self, items) -> lark.Token:
        """
        :param items:
        :return:
        """

        var_key_parts = [str(item.value) for item in items]
        var_key = '.'.join(var_key_parts)
        if len(var_key_parts) > 4:
            raise ParserValueError(
                self._merge_tokens(items, var_key),
                "Invalid variable '{}': too many name parts."
                .format(var_key))

        try:
            # This may also raise a DeferredError, but we don't want to
            # catch those.
            val = self.var_man[var_key]
        except KeyError as err:
            raise ParserValueError(
                self._merge_tokens(items, var_key),
                err.args[0])

        # Convert val into the type it looks most like.
        if isinstance(val, str):
            val = self._conv(val)

        return self._merge_tokens(items, val)

    def var_key(self, items) -> lark.Token:
        """Just return the key component."""

        return items[0]

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
            raise ParserValueError(
                token=items[0],
                message="No such function '{}'".format(func_name))

        try:
            result = func(*args)
        except functions.FunctionArgError as err:
            raise ParserValueError(
                self._merge_tokens(items, None),
                "Invalid arguments: {}".format(err))
        except functions.FunctionPluginError as err:
            # The function plugins give a reasonable message.
            raise ParserValueError(self._merge_tokens(items, None), err.args[0])

        return self._merge_tokens(items, result)

    def INTEGER(self, tok) -> lark.Token:
        """Convert to an int.

        :param lark.Token tok:
        """

        # Ints are a series of digits, so this can't fail
        tok.value = int(tok.value)
        return tok

    def FLOAT(self, tok: lark.Token) -> lark.Token:
        """Convert to a float.

        :param lark.Token tok:
        """

        # Similar to ints, this can't fail either.
        tok.value = float(tok.value)
        return tok

    def BOOL(self, tok: lark.Token) -> lark.Token:
        """Convert to a boolean."""

        # Assumes BOOL only matches 'True' or 'False'
        tok.value = tok.value == 'True'

        return tok

    def ESCAPED_STRING(self, tok: lark.Token) -> lark.Token:
        """Remove quotes and escapes from the given string."""

        # I cannot think of a string that will make this fail that will
        # also be matched as a token...
        tok.value = ast.literal_eval(tok.value)
        return tok

    def _conv(self, value):
        """Try to convert 'value' to a number or bool. Otherwise leave
        as a string."""

        try:
            return int(value)
        except ValueError:
            pass

        try:
            return float(value)
        except ValueError:
            pass

        if value in ('True', 'False'):
            return bool(value)

        return value


class VarRefVisitor(lark.Visitor):
    """Finds all of the variable references in the tree."""

    def __default__(self, tree):
        """By default, return an empty list for each subtree, as
        most trees will have no variable references."""

        return None

    def visit(self, tree):
        """Visit the tree bottom up and return all the variable references
        found."""

        var_refs = []

        for subtree in tree.iter_subtrees():
            var_ref = self._call_userfunc(subtree)
            if var_ref is not None:
                if var_ref not in var_refs:
                    var_refs.append(var_ref)

        return var_refs

    # We're not supporting this method (always just use .visit())
    visit_topdown = None

    def var_ref(self, tree: lark.Tree) -> [str]:

        var_parts = []
        for val in tree.scan_values(lambda c: True):
            var_parts.append(val)

        var_name = '.'.join(var_parts)

        return var_name
