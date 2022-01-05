class DeferredVariable:
    """The value for some variables may not be available until a test is
actually running. Deferred variables act as a placeholder in such
circumstances, and output an escape sequence when converted to a str.
"""

    # NOTE: Other than __init__, this should always have the same interface
    # as VariableList.

    def get(self, index, sub_var):      # pylint: disable=no-self-use
        """Deferred variables should never have their value retrieved."""

        # This should always be caught before this point.
        raise RuntimeError(
            "Attempted to get the value of a deferred variable."
        )

    def __len__(self):
        """Deferred variables always have a single value."""

        # This should always be caught before this point.
        raise RuntimeError(
            "Attempted to get the length of a deferred variable."
        )

    DEFERRED_PREFIX = '!deferred!'

    @classmethod
    def was_deferred(cls, val):
        """Return true if config item val was deferred when we tried to resolve
        the config.

        :param str val: The config value to check.
        :rtype: bool
        """

        return val.startswith(cls.DEFERRED_PREFIX)
