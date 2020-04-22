"""Grammar and transformation for Pavilion string syntax."""

import lark
from .common import ParseError, PavTransformer
from .expressions import VarRefVisitor

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

    def start(self, items):
        return items[0].value

    def string(self, items):
        print('string', items)

        return self._merge_tokens(items, items)

    def expr(self, items):
        """

        :param list[lark.Token] items:
        :return:
        """

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
            'format': expr_format,
        }

        return self._merge_tokens(items, value, type_=self.EXPRESSION)

    def escape(self, items):
        print('escape', items)

        token = items[0]
        token.value = token.value[1]

        return token

    def iter(self, items: [lark.Token]) -> lark.Token:
        """
        :param items:
        :return:
        """

        # The original tokens will be set as the inner value.
        inner_items = items.pop(0).value
        if items:
            separator = items.pop().value
        else:


    def separator(self, items):

        return self._merge_tokens()




    def iter_inner(self, items):
        """Works just like a string production, but repeaters aren't
        allowed."""

        return self._merge_tokens(items, items)

    def blerg(self, items):

        value = items[0].value
        if len(items) == 2:
            # Chop of the starting ':'
            format_spec = items[1][1:]
        else:
            format_spec = None

        if not isinstance(value, (int, float, bool, str)):
            type_name = type(value).__name__
            raise ParseError(
                items[0],
                "Pavilion expressions must resolve to a string, int, float, "
                "or boolean. Instead, we got {} '{}'"
                    .format('an' if type_name[0] in 'aeiou' else 'a',
                            type_name)
            )

        if format_spec is not None:
            try:
                value = '{value:{format_spec}}'.format(
                    format_spec=format_spec,
                    value=value)
            except ValueError as err:
                raise ParseError(
                    items[1],
                    "Invalid format_spec '{}': {}"
                        .format(format_spec, err))
        else:
            value = str(value)


