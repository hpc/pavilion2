"""Exceptions raised through parsing."""

import lark


class ParseError(ValueError):
    """A value error that contains the problematic token."""
    def __init__(self, token, message):
        super().__init__(message)

        self.token = token


class PavTransformer(lark.Transformer):
    """In pavilion the transformer always passes up tokens to better track
    where in the syntax things went wrong."""

    def __init__(self, var_man):
        """Initialize the transformer.

        :param pavilion.test_config.variables.VariableSetManager var_man:
            The variable manager to use to resolve references.
        """

        self.var_man = var_man
        super().__init__()

    def _merge_tokens(self, tokens, value, type_='<merged>'):
        """asdfasdf

        :param list[lark.Token] tokens:
        :return:
        """

        if not tokens:
            return lark.Token(
                value=value,
                type_='<empty>',
            )

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
            type_=type_,
            value=value,
            line=line,
            column=column,
            end_line=end_line,
            end_column=end_column,
            pos_in_stream=pos_in_stream,
            end_pos=end_pos
        )
