"""Grammar and transformation for Pavilion string syntax.

String LALR Grammar
~~~~~~~~~~~~~~~~~~~

.. code-block:: none

    {}
"""

import lark
from .common import ParserValueError, PavTransformer
from .expressions import get_expr_parser, ExprTransformer, VarRefVisitor

STRING_GRAMMAR = r'''
// All strings resolve to this token. 
start: string TRAILING_NEWLINE?

TRAILING_NEWLINE: /\n/

// It's important that each of these start with a terminal, rather than 
// a reference back to the 'string' rule. A 'STRING' terminal (or nothing) 
// is definite, but a 'string' would be non-deterministic.
string: STRING?
      | STRING? iter string
      | STRING? expr string

iter: _ITER_STRING_START iter_inner SEPARATOR
_ITER_STRING_START: "[~"
SEPARATOR.2: _TILDE _STRING_ESC _CLOSE_BRACKET
_TILDE: "~"
_CLOSE_BRACKET: "]"

iter_inner: STRING?
          | STRING? expr iter_inner
    

expr: _START_EXPR EXPR? (ESCAPED_STRING EXPR?)* FORMAT? _END_EXPR
_START_EXPR: "{{"
_END_EXPR: "}}"
EXPR: /[^}~{":]+/
// Match anything enclosed in quotes as long as the last 
// escape doesn't escape the close quote.
// A minimal match, but the required close quote will force this to 
// consume most of the string.
_STRING_ESC_INNER: /.*?/
// If the string ends in a backslash, it must end with an even number
// of them.
_STRING_ESC: _STRING_ESC_INNER /(?<!\\)(\\\\)*?/
ESCAPED_STRING : "\"" _STRING_ESC "\""

// This regex matches the whole format spec for python.
FORMAT: /:(.?[<>=^])?[+ -]?#?0?\d*[_,]?(.\d+)?[bcdeEfFgGnosxX%]?/

// Strings must start with:
//  - A closing expression '}}', a closing iteration '.]', an opening
//    iteration '[~', or the start of input.
//    - Look-behind assertions must be equal length static expressions,
//      which is why we have to match '.]' instead of just ']', and why
//      we can't match the start of the string in the look-behind.
//  - Strings can contain anything, but they can't start with an open
//    expression '{{' or open iteration '[~'.
//  - Strings cannot end in an odd number of backslashes (that would 
//    escape the closing characters).
//  - Strings must end with the end of string, an open expression '{{',
//    an open iteration '[~', or a tilde.
//  - If this is confusing, look at ESCAPED_STRING above. It's uses the
//    same basic structure, but is only bookended by quotes.
STRING: /((?<=}}|.\]|\[~)|^)/ _STRING_INNER /(?=$|}}|{{|\[~|~)/
_STRING_INNER: /(?!{{|\[~|~|}})(.|\s)+?(?<!\\)(\\\\)*/
'''

__doc__ = __doc__.format('\n    '.join(STRING_GRAMMAR.split('\n')))

_STRING_PARSER = None


def get_string_parser(debug=False):
    """Return a string parser, from cache if possible."""
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


class ExprToken(lark.Token):
    """Denotes a special token that represents an expression."""


class StringTransformer(PavTransformer):
    """Dynamically transform parsed strings into their final value.

    - string productions always return a list of tokens.
    - ExprTokens are generated for expressions.
    - These lists are collapsed by both 'start' and 'sub_string' productions.

      - The collapsed result is a single token.
      - The collapse process resolves all ExprTokens.
    - All other productions collapse their components immediately.
    """

    EXPRESSION = '<expression>'

    def __init__(self, var_man):
        """Initialize the transformer.

        :param pavilion.test_config.variables.VariableSetManager var_man:
            The variable manager to use to resolve references.
        """

        self.var_man = var_man
        super().__init__()

    def start(self, items) -> str:
        """Resolve the final string components, and return just a string.

        :param list[lark.Token] items: A single token of string components.
        """

        parts = []
        for item in items[0].value:
            if item.type == self.EXPRESSION:
                parts.append(self._resolve_expr(item, self.var_man))
            else:
                parts.append(item.value)

        # Add a trailing newline if necessary.
        if len(items) > 1:
            parts.append('\n')

        return ''.join(parts)

    def string(self, items) -> lark.Token:
        """Strings are merged into a single token whose value is all
        substrings. We're essentially just preserving the tree.

        :param list[lark.Token] items: The component tokens of the string.
        """

        token_list = []
        for item in items:
            if isinstance(item.value, list):
                token_list.extend(item.value)
            elif isinstance(item.value, dict):
                token_list.append(item)
            else:
                item.value = self._unescape(
                    item.value, {'\\{{': '{{', '\\~': '~',
                                 '\\\\{{': '\\{{', '\\\\~': '\\~'})

                token_list.append(item)

        return self._merge_tokens(items, token_list)

    @classmethod
    def expr(cls, items) -> lark.Token:
        """Grab the expression and format spec and combine them into a single
        token. We can't resolve them until we get to an iteration or the
        start. The merged expression tokens are set to the
        ``self.EXPRESSION`` type later identification, and have a dict
        of {'format_spec': <spec>, 'expr': <expression_string>} for a value.

        :param list[lark.Token] items: The expr components and possibly a
            format_spec.
        """

        # Return an empty, regular token
        if not items:
            return lark.Token(
                type_='<empty>',
                value='',
            )

        if items[-1].type == 'FORMAT':
            expr_format = items.pop()
        else:
            expr_format = None

        value = {
            'expr': ''.join([item.value for item in items]),
            'format_spec': expr_format,
        }

        return cls._merge_tokens(items, value, type_=cls.EXPRESSION)

    def iter(self, items: [lark.Token]) -> lark.Token:
        """Handle an iteration section. These can contain anything except
        nested iteration sections. This part of the string will be repeated for
        every combination of used multi-valued variables (that don't specify
        an index). The returned result is a single token that is fully
        resolved and combined into a single string.

        :param items: The 'iter_inner' token and a separator token. The value
            of 'iter_inner' will be a list of Tokens including strings,
            escapes, and expressions.
        """

        # The original tokens will be set as the inner value.
        inner_items = items[0].value
        separator = self._unescape(items[1].value[1:-1],
                                   {'\\]': ']', '\\\\]': '\\]'})

        expressions = [item for item in inner_items
                       if item.type == self.EXPRESSION]

        visitor = VarRefVisitor()
        used_vars = []

        expr_trees = {}

        for expr in expressions:
            expr_tree = self.parse_expr(expr)
            expr_trees[expr] = expr_tree

            # Get the used variables from the expression.
            used_vars.extend(visitor.visit(expr_tree))

        # Get a set of the (var_set, var) tuples used in expressions that
        # aren't specifically indexed.
        filtered_vars = []
        direct_refs = set()
        for var_name in used_vars:
            var_set, var, idx, sub_var = self.var_man.resolve_key(var_name)
            if idx is None:
                if (var_set, var) not in filtered_vars:
                    filtered_vars.append((var_set, var))
            else:
                direct_refs.add((var_set, var, idx, sub_var))

        # Make sure no direct references were used to variables we'll be
        # iterating over.
        for direct_ref in direct_refs:
            var_set, var, idx, sub_var = direct_ref
            if (var_set, var) in filtered_vars:
                key = self.var_man.key_as_dotted(direct_ref)
                raise ParserValueError(
                    token=self._merge_tokens(items, None),
                    message="Variable {} was referenced, but is also being "
                    "iterated over. You can't do both.".format(key)
                )

        # Get a variable manager for each permutation.
        var_men = self.var_man.get_permutations(filtered_vars)

        # Resolve iteration string and expression for each permutation.
        iterations = []
        for var_man in var_men:
            parts = []
            for item in inner_items:
                if item.type == self.EXPRESSION:
                    tree = expr_trees[item]
                    parts.append(self._resolve_expr(item, var_man, tree=tree))
                else:
                    parts.append(item.value)

            iterations.append(''.join(parts))

        return self._merge_tokens(items, separator.join(iterations))

    @staticmethod
    def _unescape(text, escapes) -> str:
        """Pavilion mostly relies yaml to handle un-escaping strings. There,
        are, however, a few contexts where additional escapes are necessary.

        :param str text: The text to escape.
        :param dict escapes: A dictionary of extra escapes to apply.
            Backslashes are always escapable.

        :return:
        """

        pos = 0
        text_parts = []
        while pos < len(text):
            idx = text.find('\\', pos)
            if idx == -1:
                break

            for esc_key in escapes:
                # Look for one of our escape sequences.
                if text[idx:idx+len(esc_key)] == esc_key:
                    text_parts.append(text[pos:idx])
                    text_parts.append(escapes[esc_key])
                    pos = idx + len(esc_key)
                    break
            else:
                # Skip the backslash
                text_parts.append(text[pos:idx+1])
                pos = idx + 1

        text_parts.append(text[pos:])

        out = ''.join(text_parts)

        return out

    @staticmethod
    def parse_expr(expr: lark.Token) -> lark.Tree:
        """Parse the given expression token and return the tree."""

        try:
            return get_expr_parser().parse(expr.value['expr'])
        except ParserValueError as err:
            err.pos_in_stream += expr.pos_in_stream
            # Re-raise the corrected error
            raise
        except lark.UnexpectedInput as err:
            err.pos_in_stream += expr.pos_in_stream
            # Alter the error state to make sure it can be differentiated
            # from string_parser states.
            err.state = 'expr-{}'.format(err.state)
            raise

    def _resolve_expr(self,
                      expr: lark.Token, var_man,
                      tree=None) -> str:
        """Resolve the value of the the given expression token.
        :param expr: An expression token. The value will be a dict
            of the expr string and the formatter.
        :param pavilion.test_config.variables.VariableSetManager var_man:
            The variable set manager to use to resolve this expression.
        :param lark.Tree tree: The already parsed syntax tree for expr (will
            parse for you if not given).
        :return:
        """

        if tree is None:
            tree = self.parse_expr(expr)

        transformer = ExprTransformer(var_man)
        try:
            value = transformer.transform(tree)
        except ParserValueError as err:
            err.pos_in_stream += expr.pos_in_stream
            raise

        if not isinstance(value, (int, float, bool, str)):
            type_name = type(value).__name__
            raise ParserValueError(
                expr,
                "Pavilion expressions must resolve to a string, int, float, "
                "or boolean. Instead, we got {} '{}'"
                .format('an' if type_name[0] in 'aeiou' else 'a', type_name))

        format_spec = expr.value['format_spec']

        if format_spec is not None:
            try:
                value = '{value:{format_spec}}'.format(
                    format_spec=format_spec[1:],
                    value=value)
            except ValueError as err:
                raise ParserValueError(
                    expr,
                    "Invalid format_spec '{}': {}"
                    .format(format_spec, err.args[0]))
        else:
            value = str(value)

        return value

    @staticmethod
    def _displace_token(base: lark.Token, inner: lark.Token):
        """Inner is assumed to be a token from within the 'base' string.
        Displace the position information in 'inner' so that the positions
        point to the same location in base."""

        inner.pos_in_stream = base.pos_in_stream + inner.pos_in_stream
        inner.end_pos = base.pos_in_stream + inner.end_pos
        inner.line = base.line + inner.line
        inner.column = base.column + inner.column
        inner.end_line = base.line + inner.end_line
        inner.end_column = base.end_column + inner.end_column

    def iter_inner(self, items):
        """Works just like a string production, but repeaters aren't
        allowed."""

        flat_items = []
        for item in items:
            if isinstance(item.value, list):
                flat_items.extend(item.value)
            else:
                flat_items.append(item)

        return self._merge_tokens(items, flat_items)


class StringVarRefVisitor(VarRefVisitor):
    """Parse expressions and get all used variables. """

    @staticmethod
    def expr(tree: lark.Tree) -> [str]:
        """Parse the expression, and return any used variables."""

        expr = StringTransformer.expr(tree.children)
        expr_tree = StringTransformer.parse_expr(expr)
        visitor = VarRefVisitor()

        var_list = visitor.visit(expr_tree)
        return var_list
