"""This module holds various exception classes, mainly to prevent cyclic import
problems."""

import re
import pprint
import textwrap
import shutil
import traceback

import lark

import yc_yaml


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

        self._msg = msg
        self.prior_error = prior_error
        self.data = data
        super().__init__(msg)

    @property
    def msg(self):
        """Just return msg. This exists to be overridden in order to allow for
        dynamically generated messages."""

        return self._msg

    def __reduce__(self):
        return type(self), (self.msg, self.prior_error, self.data)

    def __str__(self):
        if self.prior_error:
            return '{}: {}'.format(self.msg, str(self.prior_error))
        else:
            return self.msg

    def pformat(self, show_traceback: bool = False) -> str:
        """Specially format the exception for printing."""

        if show_traceback:
            return traceback.format_exception(self)

        lines = []
        next_exc = self.prior_error
        width = shutil.get_terminal_size((80, 80)).columns
        tab_level = 0
        for line in str(self.msg).split('\n'):
            lines.extend(textwrap.wrap(line, width=width))

        # Add any included data.
        if self.data:
            data = pprint.pformat(self.data, width=width - tab_level*2)
            for line in data.split('\n'):
                lines.append(tab_level*self.TAB_LEVEL + line)

        while next_exc:
            tab_level += 1
            indent = tab_level * self.TAB_LEVEL
            if isinstance(next_exc, PavilionError):
                next_msg = next_exc.msg
                if not isinstance(next_msg, str):
                    next_msg = str(next_msg)

                msg_parts = next_msg.split('\n')
                for msg_part in msg_parts:
                    lines.extend(textwrap.wrap(msg_part, width, initial_indent=indent,
                                               subsequent_indent=indent + self.TAB_LEVEL))
                if next_exc.data:
                    data = pprint.pformat(next_exc.data, width=width - tab_level * 2)
                    for line in data.split('\n'):
                        lines.append(indent + line)

                next_exc = next_exc.prior_error

            elif isinstance(next_exc, yc_yaml.YAMLError):
                if next_exc.context is not None:
                    lines.append(indent + next_exc.context)
                    ctx_mark = next_exc.context_mark
                    prob_mark = next_exc.problem_mark
                elif next_exc.problem:
                    # Not all yaml exceptions have context info.
                    ctx_mark = prob_mark = next_exc.problem_mark
                else:
                    # Some might not have any info (no known cases)
                    for line in str(next_exc).split('\n'):
                        lines.append(indent + line)
                    break

                # Try to open the yaml file to pinpoint the issue.
                try:
                    with open(ctx_mark.name) as yaml_file:
                        file_lines = yaml_file.readlines()
                except OSError:
                    lines.append(indent + str(next_exc.problem))
                    break

                prior = max([ctx_mark.line-2, 0])
                final = min([prob_mark.line+2, len(file_lines)-1])
                digits = len(str(final))

                for i in range(prior, final+1):
                    lines.append('{}{:{digits}}: {}'
                                 .format(indent, i, file_lines[i].rstrip(), digits=digits))
                    if i == ctx_mark.line:
                        lines.append(indent + ' '*(ctx_mark.column + digits + 2) + '^')
                    elif i == prob_mark.line:
                        lines.append(indent + ' '*(prob_mark.column + digits + 2) + '^')

                lines.append(indent + str(next_exc.problem))
                break
            else:
                if hasattr(next_exc, 'args') \
                       and isinstance(next_exc.args, (list, tuple)) \
                       and next_exc.args \
                       and isinstance(next_exc.args[0], str):
                    msg = next_exc.args[0]
                else:
                    msg = str(next_exc)

                msg_parts = str(msg).split('\n')
                for msg_part in msg_parts:
                    lines.extend(textwrap.wrap(msg_part, width, initial_indent=indent,
                                               subsequent_indent=indent))
                break

        return '\n'.join(lines)

    def __eq__(self, other):
        """Check that all values are the same."""

        if not isinstance(other, self.__class__):
            return False

        for key, value in self.__dict__.items():
            if not hasattr(other, key):
                return False

            other_value = getattr(other, key)
            if value != other_value:
                if not (value is not None and isinstance(value, other_value.__class__)):
                    return False

        return True


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

    def __init__(self, message='', var_set=None, var=None, index=None, sub_var=None,
                 prior_error=None):

        self.raw_message = message
        self.var_set = var_set
        self.var = var
        if isinstance(index, str) and index.isnumeric():
            self.index = int(index)
        else:
            self.index = index
        self.sub_var = sub_var

        super().__init__(message, prior_error=prior_error)

    @property
    def msg(self):
        key = [str(self.var)]
        if self.var_set is not None:
            key.insert(0, self.var_set)
        if self.index is not None and self.index != 0:
            key.append(str(self.index))
        if self.sub_var is not None:
            key.append(self.sub_var)

        key = '.'.join(key)

        return "Error processing variable key '{}': \n{}".format(key, self.raw_message)

    def __reduce__(self):
        return type(self), (self.raw_message, self.var_set, self.var,
                            self.index, self.sub_var, self.prior_error)


class DeferredError(VariableError):
    """Raised when we encounter a deferred variable we can't resolve."""


class TestConfigError(PavilionError):
    """An exception specific to errors in configuration."""

    def __init__(self, msg, request=None, prior_error=None, data=None):
        """These specifically take the 'TestRequest' object."""

        self.request = request
        if request is not None:
            request.has_error = True

        super().__init__(msg, prior_error, data)

    def __reduce__(self):
        return type(self), (self.msg, self.request, self.prior_error, self.data)


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

    def __init__(self, msg, tests=None, prior_error=None, data=None):
        """Keep track of the tests that triggered the error."""

        self.tests = tests if tests is not None else []

        super().__init__(msg, prior_error, data)

    def __reduce__(self):
        return type(self), (self.msg, self.tests, self.prior_error, self.data)


class TestSeriesError(PavilionError):
    """An error in managing a series of tests."""


class TestSeriesWarning(PavilionError):
    """A non-fatal series error."""


class SeriesConfigError(TestConfigError):
    """For errors handling series configs."""


class SystemPluginError(PavilionError):
    """Error thrown when a system plugin encounters an error."""


class WGetError(RuntimeError):
    """Errors for the Wget subsystem."""

class TestGroupError(PavilionError):
    """Errors thrown when managing test groups."""
