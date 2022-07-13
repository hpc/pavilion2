"""This module holds various exception classes, mainly to prevent cyclic import
problems."""

import re
import textwrap


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

    def __init__(self, message, var_set=None, var=None, index=None, sub_var=None):

        self.var_set = var_set
        self.var = var
        self.index = index
        self.sub_var = sub_var

        key = [str(self.var)]
        if self.var_set is not None:
            key.insert(0, self.var_set)
        if self.index is not None and self.index != 0:
            key.append(self.index)
        if self.sub_var is not None:
            key.append(self.sub_var)

        key = '.'.join(key)

        message = "Error processing variable key '{}': {}".format(key, message)
        super().__init__(message)


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
