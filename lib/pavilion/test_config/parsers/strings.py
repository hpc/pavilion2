"""Grammar and transformation for Pavilion string syntax."""

import lark
from .common import ParseError, PavTransformer
from .expressions import VarRefVisitor, get_expr_parser, ExprTransformer

STRING_GRAMMAR = r'''

start: string

// It's important that each of these start with a terminal, rather than 
// a reference back to the 'string' rule. A 'STRING' terminal (or nothing) 
// is definite, but a 'string' would be non-deterministic.
string: STRING?
      | STRING? ESCAPE string
      | STRING? iter string
      | STRING? expr string

iter: _ITER_STRING_START iter_inner "~" separator "]"
_ITER_STRING_START: "[~"

iter_inner: STRING?
          | STRING? ESCAPE iter_inner
          | STRING? expr iter_inner

expr: "{{" EXPR? (ESCAPED_STRING EXPR?)* FORMAT? "}}"
EXPR: /[^}":]+/
_STRING_INNER: /.*?/
_STRING_ESC_INNER: _STRING_INNER /(?<!\\)(\\\\)*?/
ESCAPED_STRING : "\"" _STRING_ESC_INNER "\""

separator: STRING? (ESCAPE STRING)*

// This regex matches the whole format spec for python.
FORMAT: /:(.?[<>=^])?[+ -]?#?0?\d*[_,]?(.\d+)?[bcdeEfFgGnosxX%]?/

// A string can be empty
// This will match any characters that aren't a '{' '[' or '\\', or
// a '{' as long as it isn't followed by another '{', or
// a '[' as long as it isn't followed by a '~'. 
STRING: /([^{[\\~}]|{(?=[^{])|}(?=[^}])|\[(?=[^~]))+/
ESCAPE: /\\./
'''

_STRING_PARSER = None


def get_string_parser(var_man, debug=False):
    """Return a string parser, from cache if possible."""
    global _STRING_PARSER

    if debug or _STRING_PARSER is None:
        parser = lark.Lark(
            grammar=STRING_GRAMMAR,
            transformer=StringTransformer(var_man),
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

    def start(self, items) -> str:
        """Resolve the final string components, and return just a string.

        :param list[lark.Token] items: A single token of string components.
        """

        print('start_items', items)
        parts = []
        for item in items[0].value:
            print('start', item)
            if item.type == self.EXPRESSION:
                parts.append(self._resolve_expr(item, self.var_man))
            else:
                parts.append(item.value)

        return ''.join(parts)

    def string(self, items) -> lark.Token:
        """Strings are merged into a single token whose value is all
        substrings. We're essentially just preserving the tree.

        :param list[lark.Token] items: The component tokens of the string.
        """

        print('string', items)
        token_list = []
        for item in items:
            if isinstance(item.value, list):
                token_list.extend(item.value)
            else:
                token_list.append(item)

        return self._merge_tokens(items, token_list)

    def expr(self, items) -> lark.Token:
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

        return self._merge_tokens(items, value, type_=self.EXPRESSION)

    def escape(self, items):
        """Remove the backslash from the escaped character."""

        token = items[0]
        token.value = token.value[1]

        return token

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
        separator = items[1].value

        expressions = [item for item in inner_items
                       if item.type == self.EXPRESSION]

        visitor = VarRefVisitor()
        used_vars = set()

        expr_trees = {}

        for expr in expressions:
            expr_tree = self._parse_expr(expr)
            expr_trees[expr] = expr_tree

            # Get the used variables from the expression.
            used_vars.update(visitor.visit(expr_tree))

        # Get a set of the (var_set, var) tuples used in expressions that
        # aren't specifically indexed.
        filtered_vars = set()
        for var_name in used_vars:
            var_set, var, idx, _ = self.var_man.resolve_key(var_name)
            if idx is None:
                filtered_vars.add((var_set, var))

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

            ''.join(parts)

        return self._merge_tokens(items, separator.join(iterations))

    def _parse_expr(self, expr: lark.Token) -> lark.Tree:
        """Parse the given expression token and return the tree."""

        try:
            return get_expr_parser().parse(expr.value['expr'])
        except ParseError as err:
            self._displace_token(expr, err.token)
            # Re-raise the corrected error
            raise

    def _resolve_expr(self,
                      expr: lark.Token, var_man,
                      tree: lark.Tree = None) -> str:
        """Resolve the value of the
        :param expr: An expression token. The value will be a dict
            of the expr string and the formatter.
        :param pavilion.test_config.variables.VariableSetManager var_man:
            The variable set manager to use to resolve this expression.
        :param tree: The already parsed syntax tree for expr (will parse
            for you if not given).
        :return:
        """

        if tree is None:
            tree = self._parse_expr(expr)

        transformer = ExprTransformer(var_man)
        try:
            value = transformer.transform(tree)
        except ParseError as err:
            self._displace_token(expr, err.token)
            raise

        if not isinstance(value, (int, float, bool, str)):
            type_name = type(value).__name__
            raise ParseError(
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
                raise ParseError(
                    expr,
                    "Invalid format_spec '{}': {}"
                    .format(format_spec, err))
        else:
            value = str(value)

        return value

    def _displace_token(self, base: lark.Token,
                        inner: lark.Token):
        """Inner is assumed to be a token from within the 'base' string.
        Displace the position information in 'inner' so that the positions
        point to the same location in base."""

        inner.line = base.line + inner.line
        inner.column = base.column + inner.column
        inner.end_line = base.line + inner.end_line
        inner.end_column = base.end_column + inner.end_column

    def separator(self, items):
        """Join the separator string parts."""

        return self._merge_tokens(items,
                                  ''.join([item.value for item in items]))

    def iter_inner(self, items):
        """Works just like a string production, but repeaters aren't
        allowed."""

        return self._merge_tokens(items, items)
