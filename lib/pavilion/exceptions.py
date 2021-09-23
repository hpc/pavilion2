"""This module holds various exception classes, mainly to prevent cyclic import
problems."""


class CommandError(RuntimeError):
    """The error type commands should raise for semi-expected errors."""


class TestRunError(RuntimeError):
    """For general test errors. Whatever was being attempted has failed in a
    non-recoverable way."""


class TestRunNotFoundError(TestRunError):
    """For when we try to find an existing test, but it doesn't exist."""
