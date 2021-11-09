"""This module holds various exception classes, mainly to prevent cyclic import
problems."""


class CommandError(RuntimeError):
    """The error type commands should raise for semi-expected errors."""


class TestRunError(RuntimeError):
    """For general test errors. Whatever was being attempted has failed in a
    non-recoverable way."""


class TestRunNotFoundError(TestRunError):
    """For when we try to find an existing test, but it doesn't exist."""


class VariableError(ValueError):
    """This error should be thrown when processing variable data,
and something goes wrong."""

    def __init__(self, message, var_set=None, var=None, index=None,
                 sub_var=None):

        super().__init__(message)

        self.var_set = var_set
        self.var = var
        self.index = index
        self.sub_var = sub_var

        self.base_message = message

    def __str__(self):

        key = [str(self.var)]
        if self.var_set is not None:
            key.insert(0, self.var_set)
        if self.index is not None and self.index != 0:
            key.append(self.index)
        if self.sub_var is not None:
            key.append(self.sub_var)

        key = '.'.join(key)

        return "Error processing variable key '{}': {}" \
            .format(key, self.base_message)


class DeferredError(VariableError):
    """Raised when we encounter a deferred variable we can't resolve."""


class TestConfigError(ValueError):
    """An exception specific to errors in configuration."""
