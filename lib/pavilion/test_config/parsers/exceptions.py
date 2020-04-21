"""Exceptions raised through parsing."""


class ParseError(ValueError):
    """A value error that contains the problematic token."""
    def __init__(self, token, message):
        super().__init__(message)

        self.token = token
