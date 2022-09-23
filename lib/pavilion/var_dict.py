"""
This provides a dictionary class that can register functions to dynamically
provide ``<function_name>:<return value>`` key:value pairs. The functions are
lazily executed, and the results are cached.
"""

import inspect
import traceback
from collections import UserDict
from functools import wraps
from typing import List

from pavilion.deferred import DeferredVariable


def var_method(func):
    """This decorator marks the given function as a scheduler variable. The
    function must take no arguments (other than self)."""
    # pylint: disable=W0212

    # The scheduler plugin class will search for these.
    func._is_var_method = True
    func._is_deferable = False

    # Wrap the function function so it keeps it's base attributes.
    @wraps(func)
    def _func(self):
        # This is primarily to enforce the fact that these can't take arguments

        value = func(self)
        norm_value = normalize_value(value)
        if norm_value is None:
            raise ValueError(
                "Invalid variable value returned by {}: {}."
                .format(func.__name__, value))

        return norm_value

    return _func


def dfr_var_method(*sub_keys):
    """This decorator marks the following function as a deferred variable. It
    can optionally be given sub_keys for the variable as positional
    arguments.

    :param list(str) sub_keys: The variable sub-keys.
    """

    # The deferred variable class expects a list.
    sub_keys = list(sub_keys)

    # You can use this decorator without arguments. In that case it will
    # still get a first argument that is the function to decorate.
    given_func = None
    if sub_keys and callable(sub_keys[0]):
        given_func = sub_keys[0]

    # This is the actual decorator that will be used.
    def _dfr_var(func):

        # The scheduler plugin class will search for these.
        # pylint: disable=W0212
        func._is_var_method = True
        func._is_deferable = True

        @wraps(func)
        def defer(self):
            """Return a deferred variable if we aren't on a node."""
            if self._deferred:
                return DeferredVariable()
            else:
                value = func(self)
                norm_val = normalize_value(value)
                if norm_val is None:
                    raise ValueError(
                        "Invalid variable value returned by {}: {}."
                        .format(func.__name__, value))
                return norm_val

        return defer

    if given_func is not None:
        return _dfr_var(given_func)
    else:
        return _dfr_var


def normalize_value(value, level=0):
    """Normalize a value to one compatible with Pavilion variables. This
    means it must be a dict of strings, a list of strings, a list of dicts of
    strings, or just a string. Returns None on failure.
    :param value: The value to normalize.
    :param level: Controls what structures are allowed as this is called
    recursively.
    """
    if isinstance(value, str):
        return value
    elif isinstance(value, (int, float, bool, bytes)):
        return str(value)
    elif isinstance(value, (list, tuple)) and level == 0:
        return [normalize_value(v, level=1) for v in value]
    elif isinstance(value, dict) and level < 2:
        return {str(k): normalize_value(v, level=2)
                for k, v in value.items()}
    else:
        return None


class VarDict(UserDict):
    """A dictionary for defining dynamic variables in Pavilion.

    Usage:
    To add a variable, create a method and decorate it with
    either ``@var_method`` or ``@dfr_var_method()``. The method name will be the
    variable name, and the method will be called to resolve the variable
    value. Methods that start with '_' are ignored.
    """

    DEFER_ERRORS = False

    def __init__(self, name, deferred=True):
        """Initialize the scheduler var dictionary.
        :param str name: The name of this var dict.
        """

        super().__init__(self)

        self._name = name
        self._deferred = deferred

        self._keys = self._find_vars()
        self._errors = []

    def _find_vars(self):
        """Find all the scheduler variables and add them as variables."""

        keys = set()
        for key, member in inspect.getmembers(self):

            # Ignore anything that starts with an underscore
            if key.startswith('_'):
                continue

            if callable(member) and getattr(member, '_is_var_method', False):
                keys.add(key)
        return keys

    def __getitem__(self, key):
        """As per the dict class."""
        if key not in self._keys:
            raise KeyError("Invalid {} variable '{}'"
                           .format(self._name, key))

        if key not in self.data:
            try:
                self.data[key] = getattr(self, key)()
            # pylint: disable=broad-except
            except Exception as err:
                # If we're deferring errors, save the given error and
                # set the value to an error message.
                if self.DEFER_ERRORS:
                    formatted_err = traceback.format_exc()
                    msg = "Error getting key '{}' (See logs for full traceback): {}"\
                          .format(key, err)
                    self.data[key] = "<{}>".format(msg)
                    self._errors.append(msg + '\n' + formatted_err)
                else:
                    # If we're not deferring errors, just re-raise it.
                    raise

        return self.data[key]

    @var_method
    def errors(self):
        """Return the list of retrieval errors encountered when using this var_dict.
        Key errors are not included."""
        return self._errors

    def add_errors(self, errors: List[str]):
        """Add the given errors to the error list."""

        self._errors.extend(errors)

    def keys(self):
        """As per the dict class."""
        return (k for k in self._keys)

    def get(self, key, default=None):
        """As per the dict class."""
        if key not in self._keys:
            return default

        return self[key]

    def values(self):
        """As per the dict class."""
        return (self[k] for k in self.keys())

    def items(self):
        """As per the dict class."""

        return ((k, self[k]) for k in self.keys())

    def info(self, key):
        """Get an info dictionary about the given key."""

        if key not in self._keys:
            raise KeyError("Key '{}' does not exist in vardict '{}'"
                           .format(key, self._name))

        func = getattr(self, key)

        # Get rid of newlines
        help_text = func.__doc__.replace('\n', ' ')
        # Get rid of extra whitespace
        help_text = ' '.join(help_text.split())

        return {
            'name': key,
            # pylint: disable=W0212
            'deferred': func._is_deferable,
            'help': help_text,
        }
