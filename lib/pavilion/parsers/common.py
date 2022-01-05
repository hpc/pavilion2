"""This module contains base classes and exceptions shared by the various
Pavilion parsers."""

import lark


class ParserValueError(lark.LarkError):
    """A value error that contains the problematic token and its position."""

    def __init__(self, token: lark.Token, message: str):
        super().__init__(message)

        self.token = token
        self.pos_in_stream = token.pos_in_stream

    # Steal the get_context method
    get_context = lark.UnexpectedInput.get_context


class PavTransformer(lark.Transformer):
    """Transformers walk the parse tree and modify it. In our case, we'll
    be resolving it into a final value. Our transformer always passes up
    tokens to better track where in the syntax things went wrong,
    and more carefully handles exceptions."""

    def _call_userfunc_token(self, token):
        """Call the user defined function for handling the given token.

        Replaces the original, which re-throws VisitorErrors on most
        exceptions. We'd rather catch and handle those ourselves."""

        try:
            func = getattr(self, token.type)
        except AttributeError:
            return self.__default_token__(token)
        else:
            return func(token)

    def _call_userfunc(self, tree, new_children=None):
        """Call the user defined function for handling the given tree.

        Replaces the original, which re-throws VisitorErrors on most
        exceptions. We'd rather catch and handle those ourselves."""

        # Assumes tree is already transformed
        children = new_children if new_children is not None else tree.children
        try:
            func = getattr(self, tree.data)
        except AttributeError:
            return self.__default__(tree.data, children, tree.meta)
        else:
            wrapper = getattr(func, 'visit_wrapper', None)
            if wrapper is not None:
                return func.visit_wrapper(func, tree.data, children, tree.meta)
            else:
                return func(children)

    @staticmethod
    def _merge_tokens(tokens, value, type_='<merged>'):
        """As tokens are resolved, we pass up a single, merged token
        that retains awareness of all the text that contributed to its value.
        This is generally necessary because of type errors, as we don't
        immediately know when a type is inappropriate. Consider::
        {{ 1 + reverse("hello") }}

        The ``reverse()`` function may accept a string, but we can't add
        1 to the returned (string) result. The whole of the function call
        is thus erroneous, rather than any single component of it.

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

            if (pos_in_stream is None or
                    tok.pos_in_stream is not None and
                    pos_in_stream > tok.pos_in_stream):
                pos_in_stream = tok.pos_in_stream

            if (end_pos is None or
                    tok.end_pos is not None and
                    end_pos > tok.pos_in_stream):
                end_pos = tok.pos_in_stream

            if line is None:
                line = tok.line
                column = tok.column
            elif tok.line is None:
                pass
            elif tok.line < line:
                line = tok.line
                column = tok.column
            elif tok.line == line:
                column = tok.column

            if end_line is None:
                end_line = tok.end_line
                end_column = tok.end_column
            elif tok.end_line is None:
                pass
            elif tok.end_line > end_line:
                end_line = tok.end_line
                end_column = tok.end_column
            elif tok.end_line == end_line:
                end_column = tok.end_column

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
