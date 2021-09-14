"""This module holds various exception classes, mainly to prevent cyclic import
problems."""


class CommandError(RuntimeError):
    """The error type commands should raise for semi-expected errors."""
