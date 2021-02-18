"""Grammar and transformer for Pavilion expression syntax.

.. code-block:: none

    {}
"""

import ast
from typing import Dict, Callable, Any

import lark
import pavilion.expression_functions.common
from pavilion import expression_functions as functions
from pavilion.utils import auto_type_convert
from .common import PavTransformer, ParserValueError

EXPR_GRAMMAR = r'''

// All expressions will resolve to the start expression.
start: expr _WS?
     |          // An empty string is valid 
     
// Trailing whitespace is ignored. Whitespace between tokens is
// ignored below.
_WS: /\s+/

expr: or_expr

// These set order of operations. 
// See https://en.wikipedia.org/wiki/Operator-precedence_parser
or_expr: and_expr ( "or" and_expr )*        
and_expr: not_expr ( "and" not_expr )*
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

// A function call can contain zero or more arguments. 
function_call: NAME "(" (expr ("," expr)*)? ")"

negative: (MINUS|PLUS) primary

// A literal value is just what it appears to be.
literal: INTEGER
       | FLOAT
       | BOOL
       | ESCAPED_STRING
       
// Allows for trailing commas
list_: L_BRACKET (expr ("," expr)* ","?)? R_BRACKET

// Variable references are kept generic. We'll use this both
// for Pavilion string variables and result calculation variables.
var_ref: NAME ("." var_key)*
var_key: NAME
        | INTEGER
        | TIMES

// Strings can contain anything as long as they don't end in an odd
// number of backslashes, as that would escape the closing quote.
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

// Names can be lower-case or capitalized, but must start with a letter or 
// underscore
NAME.1: /[a-zA-Z_][a-zA-Z0-9_]*/

// Ignore all whitespace between tokens. 
%ignore  / +(?=[^.])/
'''

_EXPR_PARSER = None

__doc__ = __doc__.format('\n    '.join(EXPR_GRAMMAR.split('\n')))


def get_expr_parser(debug=False):
    """Return an expression parser (cached if possible)."""

    global _EXPR_PARSER  # pylint: disable=global-usage

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


class BaseExprTransformer(PavTransformer):
    """Transforms the expression parse tree into an actual value.  The
    resolved value will be one of the literal types."""

    # pylint: disable=no-self-use,invalid-name

    NUM_TYPES = (
        int,
        float,
        bool
    )

    def _apply_op(self, op_func: Callable[[Any, Any], Any],
                  arg1: lark.Token, arg2: lark.Token, allow_strings=True):
        """"""

        # Verify that the arg value types are something numeric, or that it's a
        # string and strings are allowed.
        for arg in arg1, arg2:
            if isinstance(arg.value, list):
                for val in arg.value:
                    if (isinstance(val, str) and not allow_strings and
                            not isinstance(val, self.NUM_TYPES)):
                        raise ParserValueError(
                            token=arg,
                            message="Non-numeric value '{}' in list in math "
                                    "operation.".format(val))
            else:
                if (isinstance(arg.value, str) and not allow_strings and
                        not isinstance(arg.value, self.NUM_TYPES)):
                    raise ParserValueError(
                        token=arg1,
                        message="Non-numeric value '{}' in math operation."
                        .format(arg.value))

        if (isinstance(arg1.value, list) and isinstance(arg2.value, list)
                and len(arg1.value) != len(arg2.value)):
            raise ParserValueError(
                token=arg2,
                message="List operations must be between two equal length "
                "lists. Arg1 had {} values, arg2 had {}."
                .format(len(arg1.value), len(arg2.value)))

        val1 = arg1.value
        val2 = arg2.value

        if isinstance(val1, list) and not isinstance(val2, list):
            return [op_func(val1_part, val2) for val1_part in val1]
        elif not isinstance(val1, list) and isinstance(val2, list):
            return [op_func(val1, val2_part) for val2_part in val2]
        elif isinstance(val1, list) and isinstance(val2, list):
            return [op_func(val1[i], val2[i]) for i in range(len(val1))]
        else:
            return op_func(val1, val2)

    def start(self, items):
        """Returns the final value of the expression."""

        if not items:
            return ''

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
        or_items.reverse()
        base_tok = or_items.pop()

        while or_items:
            next_tok = or_items.pop()
            acc = self._apply_op(lambda a, b: bool(a or b), base_tok, next_tok)
            base_tok = self._merge_tokens([base_tok, next_tok], acc)

        return base_tok

    def and_expr(self, items):
        """Pass a single item up. Otherwise, apply ``'and'`` logical operations.

        :param list[lark.Token] items: Tokens to logically ``'and'``. The
            'and' terminals are not included.
        :return:
        """

        and_items = items.copy()
        and_items.reverse()
        base_tok = and_items.pop()

        while and_items:
            next_tok = and_items.pop()
            acc = self._apply_op(lambda a, b: bool(a and b),
                                 base_tok, next_tok)
            base_tok = self._merge_tokens([base_tok, next_tok], acc)

        return base_tok

    def not_expr(self, items) -> lark.Token:
        """Apply a logical not, if ``'not'`` is present.

        :param list[lark.Token] items: One or two tokens
        """

        if items[0] == 'not':
            # Ok, this is weird. _apply op is written for binary operations,
            # but to retrofit it for unary ops we just pass the same token
            # as both ops (so types can be checked) and make sure our lambda
            # doesn't use the second argument.
            val = self._apply_op(lambda a, b: not a, items[1], items[1])
            return self._merge_tokens(items, val)
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
        left = comp_items.pop()

        base_tok = self._merge_tokens([left], True)

        while comp_items:
            comparator = comp_items.pop()
            right = comp_items.pop()

            if comparator == '==':
                op_func = lambda a, b: a == b  # NOQA
            elif comparator == '!=':
                op_func = lambda a, b: a != b  # NOQA
            elif comparator == '<':
                op_func = lambda a, b: a < b   # NOQA
            elif comparator == '>':
                op_func = lambda a, b: a > b   # NOQA
            elif comparator == '<=':
                op_func = lambda a, b: a <= b  # NOQA
            elif comparator == '>=':
                op_func = lambda a, b: a >= b  # NOQA
            else:
                raise RuntimeError("Invalid comparator '{}'".format(comparator))

            result = self._apply_op(op_func, left, right)
            next_tok = self._merge_tokens([left, right], result)
            acc = self._apply_op(lambda a, b: a and b, base_tok, next_tok)
            base_tok = self._merge_tokens([base_tok, right], acc)
            left = right

        return base_tok

    def math_expr(self, items) -> lark.Token:
        """Pass single items up, otherwise, perform the chain of
        math operations. This function will be used for all binary math
        operations with a tokenized operator.

        :param list[lark.Token] items: An odd number of tokens. Every second
            token is an operator.
        """

        math_items = items.copy()
        math_items.reverse()
        base_tok = math_items.pop()
        while math_items:
            operator = math_items.pop()
            next_tok = math_items.pop()
            if operator == '+':
                op_func = lambda a, b: a + b  # NOQA
            elif operator == '-':
                op_func = lambda a, b: a - b  # NOQA
            elif operator == '*':
                op_func = lambda a, b: a * b  # NOQA
            elif operator == '/':
                op_func = lambda a, b: a / b  # NOQA
            elif operator == '//':
                op_func = lambda a, b: a // b  # NOQA
            elif operator == '%':
                op_func = lambda a, b: a % b  # NOQA

            else:
                raise RuntimeError("Invalid operation '{}' in expression."
                                   .format(operator))

            try:
                acc = self._apply_op(op_func, base_tok, next_tok,
                                     allow_strings=False)
            except ZeroDivisionError:
                # This should obviously only occur for division operations.
                raise ParserValueError(
                    self._merge_tokens([operator, next_tok], None),
                    "Division by zero")

            base_tok = self._merge_tokens([base_tok, next_tok], acc)

        return base_tok

    # This have been generalized.
    add_expr = math_expr
    mult_expr = math_expr

    def pow_expr(self, items) -> lark.Token:
        """Pass single items up, otherwise raise the first item to the
        power of the second item.
        :param list[lark.Token] items: One or two tokens
        """

        if len(items) == 2:
            result = self._apply_op(lambda a, b: a ** b, items[0], items[1],
                                    allow_strings=False)
            if isinstance(result, complex):
                raise ParserValueError(
                    self._merge_tokens(items, None),
                    "Power expression has complex result")

            return self._merge_tokens(items, result)
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

        value = items[1].value

        if items[0].value == '-':
            value = self._apply_op(lambda a, b: -a, items[1], items[1],
                                   allow_strings=False)
        elif items[0].value == '+':
            value = self._apply_op(lambda a, b: a, items[1], items[1],
                                   allow_strings=False)

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
        except pavilion.expression_functions.common.FunctionPluginError:
            raise ParserValueError(
                token=items[0],
                message="No such function '{}'".format(func_name))

        try:
            result = func(*args)
        except pavilion.expression_functions.common.FunctionArgError as err:
            raise ParserValueError(
                self._merge_tokens(items, None),
                "Invalid arguments: {}".format(err))
        except pavilion.expression_functions.common.FunctionPluginError as err:
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
        """Remove quotes from the given string."""

        tok.value = ast.literal_eval('r' + tok.value)
        return tok


class ExprTransformer(BaseExprTransformer):
    """Convert Pavilion string expressions into their final values given
    a variable manager."""

    def __init__(self, var_man):
        """Initialize the transformer.

        :param pavilion.test_config.variables.VariableSetManager var_man:
            The variable manager to use to resolve references.
        """

        self.var_man = var_man
        super().__init__()

    def var_ref(self, items) -> lark.Token:
        """Resolve a Pavilion variable reference.

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
            val = auto_type_convert(val)

        return self._merge_tokens(items, val)

    @staticmethod
    def var_key(items) -> lark.Token:
        """Just return the key component."""

        return items[0]


class EvaluationExprTransformer(BaseExprTransformer):
    """Transform result evaluation expressions into their final value.
    The result dictionary referenced for values will be updated in place,
    so subsequent uses of this will have the cumulative results.
    """

    def __init__(self, results: Dict):
        super().__init__()
        self.results = results

    def var_ref(self, items) -> lark.Token:
        """Iteratively traverse the results structure to find a value
        given a key. A '*' in the key will return a list of all values
        located by the remaining key. ('foo.*.bar' will return a list
        of all 'bar' elements under the 'foo' key.).

        :param items:
        :return:
        """

        key_parts = [item.value for item in items]
        try:
            value = self._resolve_ref(self.results, key_parts)
        except ValueError as err:
            raise ParserValueError(
                token=self._merge_tokens(items, None),
                message=err.args[0])

        return self._merge_tokens(items, value)

    def _resolve_ref(self, base, key_parts: list, seen_parts: tuple = tuple(),
                     allow_listing: bool = True):
        """Recursively resolve a variable reference by navigating dicts and
            lists using the key parts until we reach the final value. If a
            '*' is given, a list of the value found from looking up the
            remainder of the key are returned. For example, for a dict
            of lists of dicts, we might have a key 'a.*.b', which would return
            the value of the 'b' key for each item in the list at 'a'.
        :param base: The next item to apply a key lookup too.
        :param key_parts: The remaining parts of the key.
        :param seen_parts: The parts of the key we've seen so far.
        :param allow_listing: Allow '*' in the key_parts. This is turned off
            once we've seen one.
        :return:
        """

        key_parts = key_parts.copy()

        if not key_parts:
            return auto_type_convert(base)

        key_part = key_parts.pop(0)
        seen_parts = seen_parts + (key_part,)

        if key_part == '*':
            if not allow_listing:
                raise ValueError(
                    "References can only contain a single '*'.")

            if isinstance(base, dict):
                # The 'sorted' here is important, as it ensures the values
                # are always in the same order.
                return [self._resolve_ref(base[sub_base], key_parts,
                                          seen_parts, False)
                        for sub_base in sorted(base.keys())]
            elif isinstance(base, list):
                return [self._resolve_ref(sub_base, key_parts,
                                          seen_parts, False)
                        for sub_base in base]
            else:
                raise ValueError(
                    "Used a '*' in a variable name, but the "
                    "component at that point '{}' isn't a list or dict."
                    .format('.'.join(seen_parts)))

        elif isinstance(base, list):
            try:
                idx = int(key_part)
            except ValueError:
                raise ValueError(
                    "Invalid key component '{}'. The results structure at "
                    "'{}' is a list (so that component must be an integer)."
                    .format(key_part, '.'.join(seen_parts)))

            if idx >= len(base):
                raise ValueError(
                    "Key component '{}' is out of range for the list"
                    "at '{}'.".format(idx, '.'.join(seen_parts))
                )

            return self._resolve_ref(base[idx], key_parts, seen_parts,
                                     allow_listing)

        elif isinstance(base, dict):
            if key_part not in base:
                raise ValueError(
                    "Results dict does not have the key '{}'."
                    .format('.'.join([str(part) for part in seen_parts]))
                )

            return self._resolve_ref(base[key_part], key_parts, seen_parts,
                                     allow_listing)

        raise ValueError("Key component '{}' given, but value '{}' at '{}'"
                         "is a '{}' not a dict or list."
                         .format(key_part, base, '.'.join(seen_parts),
                                 type(base)))

    @staticmethod
    def var_key(items) -> lark.Token:
        """Just return the key component."""

        return items[0]


class VarRefVisitor(lark.Visitor):
    """Finds all of the variable references in an expression parse tree."""

    def __default__(self, tree):
        """By default, return an empty list for each subtree, as
        most trees will have no variable references."""

        return None

    def visit(self, tree):
        """Visit the tree bottom up and return all the variable references
        found."""

        var_refs = []

        for subtree in tree.iter_subtrees():
            refs = self._call_userfunc(subtree)
            if refs is None:
                continue

            for ref in refs:
                if ref not in var_refs:
                    var_refs.append(ref)

        return var_refs

    # We're not supporting this method (always just use .visit())
    visit_topdown = None

    @staticmethod
    def var_ref(tree: lark.Tree) -> [str]:
        """Assemble and return the given variable reference."""

        var_parts = []
        for val in tree.scan_values(lambda c: True):
            var_parts.append(val)

        var_name = '.'.join(var_parts)

        return [var_name]
