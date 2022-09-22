"""This module holds various exception classes, mainly to prevent cyclic import
problems."""

import re
import textwrap

import lark


class PavilionError(RuntimeError):
    """Base class for all Pavilion errors."""

    SPLIT_RE = re.compile(': *\n? *')
    TAB_LEVEL = '  '

    def __str__(self):
        msg = self.args[0]
        parts = self.SPLIT_RE.split(msg)

        lines = []
        for i in range(len(parts)):
            lines.extend(textwrap.wrap(parts[i], 80, initial_indent=i*self.TAB_LEVEL))

        return '\n'.join(lines)


class CommandError(PavilionError):
    """The error type commands should raise for semi-expected errors."""


class TestRunError(PavilionError):
    """For general test errors. Whatever was being attempted has failed in a
    non-recoverable way."""


class TestRunNotFoundError(TestRunError):
    """For when we try to find an existing test, but it doesn't exist."""


class VariableError(PavilionError):
    """This error should be thrown when processing variable data,
and something goes wrong."""

    def __init__(self, message='', var_set=None, var=None, index=None, sub_var=None):

        self.raw_message = message
        self.var_set = var_set
        self.var = var
        if isinstance(index, str) and index.isnumeric():
            self.index = int(index)
        else:
            self.index = index
        self.sub_var = sub_var

        key = [str(self.var)]
        if self.var_set is not None:
            key.insert(0, self.var_set)
        if self.index is not None and self.index != 0:
            key.append(str(self.index))
        if self.sub_var is not None:
            key.append(self.sub_var)

        key = '.'.join(key)

        message = "Error processing variable key '{}': {}".format(key, ''.join(message))

        super().__init__(message)

    def __reduce__(self):

        return type(self), (self.raw_message, self.var_set, self.var, self.index, self.sub_var)


class DeferredError(VariableError):
    """Raised when we encounter a deferred variable we can't resolve."""


class TestConfigError(PavilionError):
    """An exception specific to errors in configuration."""


class TestBuilderError(PavilionError):
    """Exception raised when builds encounter an error."""


class FunctionPluginError(RuntimeError):
    """Error raised when there's a problem with a function plugin
    itself."""


class FunctionArgError(ValueError):
    """Error raised when a function plugin has a problem with the
    function arguments."""


class ParserValueError(lark.LarkError, PavilionError):
    """A value error that contains the problematic token and its position."""

    def __init__(self, token: lark.Token, message: str):
        super().__init__(message)

        self.token = token
        self.pos_in_stream = token.start_pos
        self.message = message

    def __reduce__(self):
        """Properly return the original arguments when pickling."""

        return type(self), (self.token, self.message)

    # Steal the get_context method
    get_context = lark.UnexpectedInput.get_context


class StringParserError(ValueError):
    """Common error to raise when parsing problems are encountered."""

    def __init__(self, message, context):
        self.message = message
        self.context = context

        super().__init__()

    def __str__(self):
        return "\n".join([self.message, self.context])

    def __reduce__(self):
        return type(self), (self.message, self.context)


class TestSetError(PavilionError):
    """For when creating a test set goes wrong."""

