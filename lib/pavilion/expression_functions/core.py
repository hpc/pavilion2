"""Contains the base expression plugins in a single module to speed Pavilion
loading."""

import math
import random

from . import CoreFunctionPlugin, num, FunctionPluginError


class IntPlugin(CoreFunctionPlugin):
    """Convert integer strings to ints of arbitrary bases."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="int",
            description="Convert integer strings to ints of arbitrary bases.",
            arg_specs=(str, int),
        )

    @staticmethod
    def int(value, base):
        """Convert the given string 'value' as an integer of
         the given base. Bases from 2-32 are allowed."""

        return int(value, base)


class RoundPlugin(CoreFunctionPlugin):
    """Round the given number to the nearest integer."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="round",
            description="Round the given number to the nearest integer.",
            arg_specs=(float,))

    @staticmethod
    def round(val: float):
        """Round the given number to the nearest int."""

        return round(val)


class FloorPlugin(CoreFunctionPlugin):
    """Get the floor of the given number."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="floor",
            description="Return the integer floor.",
            arg_specs=(float,))

    @staticmethod
    def floor(val):
        """Round the given number down to the nearest int."""

        return math.floor(val)


class CeilPlugin(CoreFunctionPlugin):
    """Get the ceiling of the given number."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="ceil",
            description="Return the integer ceiling.",
            arg_specs=(float,))

    @staticmethod
    def ceil(val):
        """Round the given number up to the nearest int."""

        return math.ceil(val)


class SumPlugin(CoreFunctionPlugin):
    """Get the floating point sum of the given numbers."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="sum",
            description="Return the sum of the given numbers.",
            arg_specs=([num],))

    @staticmethod
    def sum(vals):
        """Get the sum of the given numbers. Will return an int if
        all arguments are ints, otherwise returns a float."""

        return sum(vals)


class AvgPlugin(CoreFunctionPlugin):
    """Get the average of the given numbers."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="avg",
            description="Returns the average of the given numbers.",
            arg_specs=([num],)
        )

    @staticmethod
    def avg(vals):
        """Get the average of vals. Will always return a float."""

        return sum(vals)/len(vals)


class LenPlugin(CoreFunctionPlugin):
    """Return the length of the given item, where item can be a string,
    list, or dict."""

    def __init__(self):
        """Setup plugin"""

        super().__init__(
            name='len',
            description='Return the integer length of the given str, int or '
                        'mapping/dict.',
            arg_specs=None,
        )

    def _validate_arg(self, arg, spec):
        if not isinstance(arg, (list, str, dict)):
            raise FunctionPluginError(
                "The list_len function only accepts lists, dicts, and "
                "strings. Got {} of type {}.".format(arg, type(arg).__name__)
            )
        return arg

    signature = "len(list|dict|str)"

    @staticmethod
    def len(arg):
        """Just return the length of the argument."""

        return len(arg)


class RandomPlugin(CoreFunctionPlugin):
    """Return a random number in [0,1)."""

    def __init__(self):
        """Setup Plugin"""

        super().__init__(
            name="random",
            description="Return a random float in [0,1).",
            arg_specs=tuple())

    @staticmethod
    def random():
        """Return a random float in [0,1)."""

        return random.random()
