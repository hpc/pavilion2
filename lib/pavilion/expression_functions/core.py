"""Contains the base expression plugins in a single module to speed Pavilion
loading."""

import math
import random
import re
from typing import List, Dict, Union

from .base import FunctionPlugin, num, Opt
from ..errors import FunctionPluginError, FunctionArgError


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


class RoundDigPlugin(CoreFunctionPlugin):
    """Round the number to N decimal places: ``round_dig(12.12341234, 3) -> 12.123``"""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="round_dig",
            arg_specs=(float, int))

    @staticmethod
    def round_dig(val: float, places: int):
        """Round the given number to the nearest int."""

        return round(val, places)


class LogPlugin(CoreFunctionPlugin):
    """Take the log of the given number to the given base."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="log",
            arg_specs=(num, num))

    @staticmethod
    def log(val: num, base: num):
        """Take the log of the given number to the given base."""

        return math.log(val, base)


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


class MaxPlugin(CoreFunctionPlugin):
    """Get the max of the given numbers."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="max",
            arg_specs=([num],)
        )

    @staticmethod
    def max(vals):
        """Get the max of vals."""

        return max(vals)


class MinPlugin(CoreFunctionPlugin):
    """Get the min of the given numbers."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="min",
            arg_specs=([num],)
        )

    @staticmethod
    def min(vals):
        """Get the min of vals."""

        return min(vals)


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
            arg_specs=({},),
        )

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
            raise FunctionArgError("Could not compile regex", err)

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


class Sqrt(CoreFunctionPlugin):
    """Calculate the square root of a given number.
    Yes, people can just do X^(1/2), but most people forget that."""

    def __init__(self):
        super().__init__(
            'sqrt',
            arg_specs=(num,))

    @staticmethod
    def sqrt(value: num):
        """Take a square root."""

        return value ** 0.5

      
class HighPassFilter(CoreFunctionPlugin):
    """Given the 'value_dict', return a new dictionary that contains only
    items that exceed 'limit'. For dicts of dicts, you must specify an item_key
    to check limit against.

    Examples:
     Given dict 'data={a: 1, b: 2, c: 3, d: 4}',
     `high_pass_filter(data, 3)` would return a dict with
     the 'c' and 'd' keys removed.

     Given dict 'data={foo: {a: 5}, bar: {a: 100}}, baz: {a: 20}}'
     `high_pass_filter(data, 20, 'a')` would return a dict containing
     only key 'foo' and its value/s."""

    def __init__(self):
        super().__init__(
            'high_pass_filter',
            arg_specs=({}, num, Opt(str)))

    @staticmethod
    def high_pass_filter(value_dict: Dict, limit: Union[int, float], item_key: str = None) -> Dict:
        """Return only items > limit"""

        new_dict = {}
        for key, values in value_dict.items():
            if isinstance(values, dict):
                if item_key is None:
                    raise FunctionArgError("value_dict contained a dict, but no key was specified.")

                value = values.get(item_key)
            else:
                if item_key is not None:
                    raise FunctionArgError(
                        "value_dict contained a non-dictionary, but a key was specified.")

                value = values

            if isinstance(value, (int, float, str)):
                value = num(value)
            else:
                continue

            if value > limit:
                new_dict[key] = values

        return new_dict


class LowPassFilter(CoreFunctionPlugin):
    """Given the 'value_dict', return a new dictionary that contains only
    items that are less than 'limit'. For dicts of dicts, you must specify
    a sub-key to check 'limit' against. See 'high_pass_filter' for examples."""

    def __init__(self):
        super().__init__(
            'low_pass_filter',
            arg_specs=({}, num, Opt(str)))

    @staticmethod
    def low_pass_filter(value_dict: Dict, limit: Union[int, float], item_key: str = None) -> Dict:
        """Return only items > limit"""

        new_dict = {}
        for key, values in value_dict.items():
            if isinstance(values, dict):
                if item_key is None:
                    raise FunctionArgError("value_dict contained a dict, but no key was specified.")

                value = values.get(item_key)
            else:
                if item_key is not None:
                    raise FunctionArgError(
                        "value_dict contained a non-dictionary, but a key was specified.")

                value = values

            if isinstance(value, (int, float, str)):
                value = num(value)
            else:
                continue

            if value < limit:
                new_dict[key] = values

        return new_dict


class Range(CoreFunctionPlugin):
    """Return a list of numbers from a..b, not inclusive of b."""

    def __init__(self):
        super().__init__(
            'range',
            arg_specs=(int, int),
            )

    @staticmethod
    def range(start, end):
        """Calculate the range."""

        vals = []
        while start < end:
            vals.append(start)
            start += 1

        return vals

      
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
                "The 'values' and 'names' arguments must be lists of equal length.")

        mean = sum(values)/len(values)
        stddev = (sum([(val - mean)**2 for val in values])/len(values))**0.5

        deviations = {}

        for i in range(len(values)):
            val = values[i]

            dev = abs(val - mean)/stddev
            if dev > limit:
                deviations[names[i]] = dev

        return deviations
