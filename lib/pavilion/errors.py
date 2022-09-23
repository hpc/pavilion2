"""This module holds various exception classes, mainly to prevent cyclic import
problems."""

import re
import pprint
import textwrap
import shutil

import lark


class PavilionError(RuntimeError):
    """Base class for all Pavilion errors."""

    SPLIT_RE = re.compile(': *\n? *')
    TAB_LEVEL = '  '

    def __init__(self, msg, prior_error=None, data=None):
        """These take a new message and whatever prior error caused the problem.

        :param msg: The error message.
        :param prior_error: The exception object that triggered this exception.
        :param data: Any relevant data that needs to be passed to the user.
        """

        self.msg = msg
        self.prior_error = prior_error
        self.data = data
        super().__init__(msg)

    def __reduce__(self):
        return type(self), (self.msg, self.prior_error, self.data)

    def __str__(self):
        if self.prior_error:
            return '{}: {}'.format(self.msg, str(self.prior_error))
        else:
            return self.msg

    def pformat(self) -> str:
        """Specially format the exception for printing."""

        lines = []
        next_exc = self.prior_error
        width = shutil.get_terminal_size((100, 100)).columns
        tab_level = 0
        indent = self.TAB_LEVEL
        lines.extend(textwrap.wrap(self.msg, width, initial_indent=indent,
                                   subsequent_indent=indent))

        # Add any included data.
        if self.data:
            data = pprint.pformat(self.data, width=width - tab_level*2)
            for line in data.split('\n'):
                lines.extend(tab_level*self.TAB_LEVEL + line)

        while next_exc:
            tab_level += 1
            indent = tab_level * self.TAB_LEVEL
            if isinstance(next_exc, PavilionError):
                lines.extend(textwrap.wrap(next_exc.msg, width, initial_indent=indent,
                                           subsequent_indent=indent))
                if next_exc.data:
                    data = pprint.pformat(next_exc.data, width=width - tab_level * 2)
                    for line in data.split('\n'):
                        lines.append((tab_level * self.TAB_LEVEL) + line)

                next_exc = next_exc.prior_error
            else:
                if hasattr(next_exc, 'args') and isinstance(next_exc.args, list):
                    msg = next_exc.args[0]
                else:
                    msg = str(next_exc)
                lines.extend(textwrap.wrap(msg, width, initial_indent=indent,
                                           subsequent_indent=indent))

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


class FunctionPluginError(PavilionError):
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


class PluginError(PavilionError):
    """General Plugin Error"""


class ResultError(PavilionError):
    """Error thrown when a failure occurs with any sort of result
    processing."""


class SchedulerPluginError(PavilionError):
    """Raised when scheduler plugins encounter an error."""


class TestSeriesError(PavilionError):
    """An error in managing a series of tests."""


class TestSeriesWarning(PavilionError):
    """A non-fatal series error."""


class SystemPluginError(PavilionError):
    """Error thrown when a system plugin encounters an error."""


class WGetError(RuntimeError):
    """Errors for the Wget subsystem."""
    pass
