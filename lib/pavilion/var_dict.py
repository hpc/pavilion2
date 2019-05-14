from collections import UserDict
from functools import wraps
import logging


def var_method(func):
    """This decorator marks the given function as a scheduler variable. The
    function must take no arguments (other than self)."""

    # The scheduler plugin class will search for these.
    func._is_var_method = True
    func._is_deferable = False

    # Wrap the function function so it keeps it's base attributes.
    @wraps(func)
    def _func(self):
        # This is primarily to enforce the fact that these can't take arguments
        return str(func(self))

    return _func


class VarDict(UserDict):
    """A dictionary for defining dynamic variables in Pavilion.

    Usage:
    To add a variable, create a method and decorate it with
    either '@var_method' or '@dfr_var_method()'. The method name will be the
    variable name, and the method will be called to resolve the variable
    value. Methods that start with '_' are ignored.
    """

    def __init__(self, name):
        """Initialize the scheduler var dictionary.
        :param str name: The name of this var dict.
        """

        super().__init__(self)

        self._name = name

        self._keys = self._find_vars()

        self.logger = logging.getLogger('{}_vars'.format(name))

    @classmethod
    def _find_vars(cls):
        """Find all the scheduler variables and add them as variables."""

        keys = set()
        for key in cls.__dict__.keys():

            # Ignore anything that starts with an underscore
            if key.startswith('_'):
                continue
            obj = getattr(cls, key)
            if callable(obj) and getattr(obj, '_is_var_method', False):
                keys.add(key)
        return keys

    def __getitem__(self, key):
        """As per the dict class."""
        if key not in self._keys:
            raise KeyError("Invalid {} variable '{}'"
                           .format(self._name, key))

        if key not in self.data:
            self.data[key] = getattr(self, key)()

        return self.data[key]

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
        return ((k, self[k]) for k in self._keys)

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
            'deferred': func._is_deferable,
            'help': help_text,
        }
