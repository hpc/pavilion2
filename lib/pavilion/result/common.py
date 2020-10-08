"""Common constants and bits for all of result handling."""

NON_MATCH_VALUES = (None, [], False)
"""Result Parser return values that are not considered to be a match."""

EMPTY_VALUES = (None, [])
"""Result Parser return values that are considered to be empty of value."""


class ResultError(RuntimeError):
    """Error thrown when a failure occurs with any sort of result
    processing."""