"""Exceptions raised through parsing."""

import lark


class ParserValueError(lark.LarkError):
    """A value error that contains the problematic token."""

    def __init__(self, token: lark.Token, message: str):
        super().__init__(message)

        self.token = token
        self.pos_in_stream = token.pos_in_stream

    # Steal the get_context method
    get_context = lark.UnexpectedInput.get_context


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


class VarRefVisitor(lark.Visitor):
    """Finds all of the variable references in a parse tree."""

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
