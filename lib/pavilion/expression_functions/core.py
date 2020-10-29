"""Contains the base expression plugins in a single module to speed Pavilion
loading."""

import math
import random
import re
from typing import List

from .base import FunctionPlugin, num
from .common import FunctionPluginError, FunctionArgError


class CoreFunctionPlugin(FunctionPlugin):
    """A function plugin that sets defaults for core plugins. Use when adding
    additional function plugins to the core_functions module. Classes that
    inherit from this will automatically be added as function plugins.  If
    adding non-core functions, use the standard plugin mechanisms."""

    core = True

    def __init__(self, name, arg_specs, description=None):
        super().__init__(name, arg_specs, description=description,
                         priority=self.PRIO_CORE)


class IntPlugin(CoreFunctionPlugin):
    """Convert integer strings to ints of arbitrary bases."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="int",
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
            arg_specs=(float,))

    @staticmethod
    def floor(val):
        """Round the given number down to the nearest int."""

        return math.floor(val)


class CeilPlugin(CoreFunctionPlugin):
    """Get the integer ceiling of the given number."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="ceil",
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
            arg_specs=None,
        )

    def _validate_arg(self, arg, spec):
        if not isinstance(arg, (list, str, dict)):
            raise FunctionPluginError(
                "The len function only accepts lists, dicts, and "
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
            arg_specs=tuple())

    @staticmethod
    def random():
        """Return a random float in [0,1)."""

        return random.random()


class KeysPlugin(CoreFunctionPlugin):
    """Return the keys of a given dict."""

    def __init__(self):
        """Setup."""

        super().__init__(
            name='keys',
            arg_specs=None,
        )

    signature = "keys(dict)"

    def _validate_arg(self, arg, spec):
        if not isinstance(arg, dict):
            raise FunctionPluginError(
                "The dicts function only accepts dicts. Got {} of type {}."
                .format(arg, type(arg).__name__))
        return arg

    @staticmethod
    def keys(arg):
        """Return a (sorted) list of keys for the given dictionary."""

        return sorted(list(arg.keys()))


class AllPlugin(CoreFunctionPlugin):
    """Return whether all of the items in the given list are true."""

    def __init__(self):
        """Setup plugin"""

        super().__init__(
            name='all',
            arg_specs=([num],)
        )

    @staticmethod
    def all(items):
        """Just use the built-in all function."""
        return all(items)


class AnyPlugin(CoreFunctionPlugin):
    """Return whether any of the items in the given list are true."""

    def __init__(self):
        """Setup plugin"""

        super().__init__(
            name='any',
            arg_specs=([num],)
        )

    @staticmethod
    def any(items):
        """Just use the built-in any function."""
        return any(items)


class RegexSearch(CoreFunctionPlugin):
    """Search for the given regular expression. Returns the matched text or,
    if a matching group (limit 1) was used, the matched group. Returns an
    empty string on no match. Regexes use Python\'s regex syntax."""

    def __init__(self):

        super().__init__(
            name='re_search',
            arg_specs=(str, str),
        )

    @staticmethod
    def re_search(regex, data):
        """Search for the given regex in data."""

        try:
            regex = re.compile(regex)
        except re.error as err:
            raise FunctionArgError(
                "Could not compile regex:\n{}".format(err.args[0])
            )

        match = regex.search(data)
        if match is None:
            return ''

        if match.groups():
            return match.groups()[0]
        else:
            return match.group()


class Replace(CoreFunctionPlugin):
    """Replace substrings from a given string."""

    def __init__(self):

        super().__init__(
            'replace',
            arg_specs=(str, str, str),
        )

    @staticmethod
    def replace(string: str, find: str, replacement: str):
        """Replace all instances of 'find' with 'replacement' in 'string'."""

        return string.replace(find, replacement)


class Outliers(CoreFunctionPlugin):
    """Calculate outliers given a list of values and a separate list
    of their associated names. The lists should be the same length, and
    in matching order (which Pavilion should generally guarantee). A value is
    flagged as an outlier if it is more than 'limit' standard deviations
    from the mean of the values.

    Produces a dict of name -> (val - mean)/stddev for only those values
    flagged as outliers.

    Ex: 'bad_nodes: 'outliers(n.*.speed, keys(n), 2.0)`
    This would find any nodes with a speed more than 2.0 std deviations
    from the mean.
    """

    def __init__(self):
        super().__init__(
            'outliers',
            arg_specs=([num], [str], float),
        )

    @staticmethod
    def outliers(values: List[num], names: List[str], limit: float):
        """Create the outlier dict."""

        if len(values) != len(names):
            raise FunctionPluginError(
                "The 'values' and 'names' arguments must be lists of equal"
                "length."
            )

        mean = sum(values)/len(values)
        stddev = (sum([(val - mean)**2 for val in values])/len(values))**0.5

        deviations = {}

        for i in range(len(values)):
            val = values[i]

            dev = abs(val - mean)/stddev
            if dev > limit:
                deviations[names[i]] = dev

        return deviations
