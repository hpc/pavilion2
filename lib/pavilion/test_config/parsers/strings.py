"""Grammar and transformation for Pavilion string syntax."""

import lark
from .exceptions import ParseError

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

expr: "{{" /.*?/ _FORMAT? "}}"

separator: STRING? (escape STRING)*

// This regex matches the whole format spec for python.
_FORMAT: /:(.?[<>=^])?[+ -]?#?0?\d*[_,]?(.\d+)?[bcdeEfFgGnosxX%]?/

// A string can be empty
// This will match any characters that aren't a '{' '[' or '\\', or
// a '{' as long as it isn't followed by another '{', or
// a '[' as long as it isn't followed by a '~'. 
STRING: /([^{[\\~}]|{(?=[^{])|}(?=[^}])|\[(?=[^~]))+/
ESCAPE: /\\./
'''


class StringTransformer(lark.Transformer):
    """Dynamically transform parsed strings into their final value."""

    def __init__(self, var_man):
        """Initialize the transformer.

        :param pavilion.test_config.variables.VariableSetManager var_man:
            The variable set manager to use to resolve expression variables.
        """

        self.var_man = var_man

        super().__init__()

    def _blerg(self, items):

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

