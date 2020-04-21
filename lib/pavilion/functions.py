"""Plugins for performing operations on both pavilion variable values
and result values."""

import inspect
import math
import logging
import re
import random

from yapsy import IPlugin

LOGGER = logging.getLogger(__file__)

# The dictionary of available function plugins.
_FUNCTIONS = {}  # type: {str,FunctionPlugin}


class FunctionPluginError(RuntimeError):
    """Error raised when there's a problem with a function plugin
    itself."""


class FunctionArgError(ValueError):
    """Error raised when a function plugin has a problem with the
    function arguments."""


def num(val):
    """Return val as an int or float, depending on what it most
    closely resembles."""

    if isinstance(val, (float, int)):
        return val
    elif val in ('True', 'False'):
        return val == 'True'
    elif isinstance(val, str):
        try:
            return int(val)
        except ValueError:
            pass

        try:
            return float(val)
        except ValueError:
            raise ValueError("Could not convert '{}' to either "
                             "int or float.")

    raise RuntimeError("Invalid value '{}' given to num.".format(val))


class FunctionPlugin(IPlugin.IPlugin):
    """Plugin base class for math functions."""

    VALID_SPEC_TYPES = (
        int,
        float,
        str,
        bool,
        num,
    )

    NAME_RE = re.compile(r'[a-zA-Z][a-zA-Z0-9_]*$')

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    def __init__(self, name, description, arg_specs,
                 priority=PRIO_COMMON):
        """
        :param str name: The name of this function.
        :param str description: A short description of this function.
        :param int priority: The plugin priority.
        :param {str,type} arg_specs: A dictionary of arg name to
            type spec for each function argument. The spec for each
            argument defines the argument structure and type. See
            the validate_arg_spec docstring for more. While this
            is a dictionary, **order matters**, and corresponds to
            the function argument order. ``None`` denotes that arg_specs
            won't be used or validated, and requires that ``_validate_arg`` be
            overridden.
        """

        if not self.NAME_RE.match(name):
            raise FunctionPluginError(
                "Invalid function name: '{}'".format(name))

        self.name = name
        self.description = description
        self.priority = priority

        if arg_specs is None:
            if self._validate_arg is FunctionPlugin._validate_arg:
                raise RuntimeError(
                    "Function plugin {} at {} was given an arg_spec of "
                    "'None', but did not override '_validate_arg'."
                    .format(self.name, self.path)
                )
        else:
            for arg_spec in arg_specs.values():
                self.validate_arg_spec(arg_spec)

        self.arg_specs = arg_specs

        super().__init__()

    def validate_arg_spec(self, arg):
        """Recursively validate the argument spec, to make sure plugin
        creators are using this right.
        :param arg: A valid arg spec is a structure of lists and
            dicts, and types from self.VALID_SPEC_TYPES.

            - Lists should contain one representative containing type.
            - Dicts should have at least one key-value pair (with string keys).
            - Dicts and lists can also be empty. Such specs denote that
            - Dict specs don't have to contain every key the dict might have,
              just those that will be used.
            - Specs may be any structure of these types, as long
              as they comply with the above rules.
            - The 'num' spec type will accept strings, floats, ints,
              or bool. ints and floats are left alone, bools become
              ints, and strings become an int or a float if they can.
        :raises FunctionPluginError: On a bad arg spec.
        """

        if isinstance(arg, list):
            if len(arg) != 1:
                raise FunctionPluginError(
                    "Invalid list spec argument. List arguments must contain "
                    "a single subtype. This had '{}'."
                    .format(arg)
                )
            self.validate_arg_spec(arg[0])

        elif isinstance(arg, dict):
            if len(arg) == 0:
                raise FunctionPluginError(
                    "Invalid dict spec argument. Dict arguments must contain "
                    "at least one key-value pair. This had '{}'"
                    .format(arg)
                )
            for key, sub_arg in arg.items():
                self.validate_arg_spec(sub_arg)

        elif not arg in self.VALID_SPEC_TYPES:
            raise FunctionPluginError(
                "Invalid spec type '{}'. Must be one of '{}'"
                .format(arg, self.VALID_SPEC_TYPES)
            )

    @property
    def path(self):
        """The path to the file containing this result parser plugin."""

        return inspect.getfile(self.__class__)

    def __call__(self, *args):
        """Validate/convert the arguments and call the function."""

        if self.arg_specs is not None:
            if len(args) != len(self.arg_specs):
                raise FunctionPluginError(
                    "Invalid number of arguments. Got {}, but expected {}"
                    .format(len(args), len(self.arg_specs)))

            # Create the full list of validated arguments.
            val_args = []
            for arg, spec in zip(args, self.arg_specs.values()):
                print('arg/spec', arg, spec)
                val_args.append(self._validate_arg(arg, spec))
        else:
            val_args = args

        try:
            return self.func(*val_args)
        except Exception as err:
            raise FunctionPluginError(
                "Error in function plugin {}: {}"
                .format(self.name, err)
            )

    @property
    def signature(self, newlines=False):
        """Generate a function signature for this function.
        :newlines: Put each argument on a separate line.
        """

        sep = ',\n' + ' '*(len(self.name) + 1) if newlines else ', '

        parts = [self.name + '(']
        for key, spec in self.arg_specs.items():
            parts.append('{}: {}'.format(key, self.spec_to_desc(spec)))

        return sep.join(parts) + ')'

    def spec_to_desc(self, spec):
        """Convert an argument spec into a descriptive structure that
        can be reasonably printed."""

        if isinstance(spec, list):
            return [self.spec_to_desc(spec[0])]
        elif isinstance(spec, dict):
            return {k: self.spec_to_desc(v) for k, v in spec.items()}
        else:
            return spec.__name__

    def _validate_arg(self, arg, spec):
        """Ensure that the argument is of the structure specified by 'spec',
        and convert all contained values accordingly.

        :param arg: The argument to validate.
        :param Union[list,dict,int,bool,str,float] spec: The spec to apply to
            this argument.
        :return: The validated, auto-converted argument.
        """

        if isinstance(spec, list):
            if not isinstance(arg, list):
                raise FunctionPluginError(
                    "Invalid argument '{}'. Expected a list."
                    .format(arg)
                )

            val_args = []
            for arg_item in arg:
                try:
                    val_args.append(self._validate_arg(arg_item, spec[0]))
                except FunctionPluginError:
                    raise FunctionPluginError(
                        "Invalid list item argument '{}'. Expected a list of "
                        "'{}'."
                        .format(arg_item, spec[0]))
            return val_args

        if isinstance(spec, dict):
            if not isinstance(arg, dict):
                raise FunctionPluginError(
                    "Invalid argument '{}'. Expected a dict."
                    .format(arg))

            val_args = {}
            for key, sub_spec in spec.items():
                if key not in arg:
                    raise FunctionPluginError(
                        "Invalid dict argument '{}'. Missing key '{}'"
                        .format(arg, key))

                try:
                    val_args[key] = self._validate_arg(arg[key], sub_spec)
                except FunctionPluginError as err:
                    raise FunctionPluginError(
                        "Invalid dict argument '{}' for key '{}': {}"
                        .format(arg[key], key, err))

            return val_args

        try:
            # Boolean strings need a little conversion help when
            # converting to other types. The num type takes care of this
            # internally.
            if spec in (int, float) and arg in ('True', 'False'):
                arg = bool(arg)

            print('spec', spec)
            return spec(arg)
        except ValueError:
            raise FunctionPluginError(
                "Invalid {} ({})"
                .format(spec.__name__, arg))

    def func(self, *args):
        """The function code. Must be overridden by the plugin. The docstring
        for this function will be used as the main, verbose documentation for
        the plugin."""

        raise NotImplementedError

    def activate(self):
        """Yapsy runs this when adding the plugin. Add our plugin
        to the registry of function plugins."""

        print('activating', self.name, self.name in _FUNCTIONS)

        if self.name in _FUNCTIONS:
            other = _FUNCTIONS[self.name]
            if self.priority > other.priority:
                LOGGER.info(
                    "Function plugin '%s' at %s is superceded by plugin at %s",
                    self.name, other.path, self.path)
                _FUNCTIONS[self.name] = self
            elif self.priority < other.priority:
                LOGGER.info(
                    "Function plugin '%s' at %s is ignored in lieu of "
                    "plugin at %s.",
                    self.name, self.path, other.path)
            else:
                raise RuntimeError(
                    "Function plugin conflict. Parser '{}' at '{}'"
                    "has the same priority as plugin at '{}'"
                    .format(self.name, self.path, other.path))

        else:
            _FUNCTIONS[self.name] = self

    def deactivate(self):
        """Yapsy runs this when removing the plugin. Plugins will
        only be removed by unit tests."""

        del _FUNCTIONS[self.name]


def get_plugin(name: str) -> FunctionPlugin:
    """Get the function plugin called 'name'."""

    if name not in _FUNCTIONS:
        raise FunctionPluginError("No such function '{}'".format(name))
    else:
        return _FUNCTIONS[name]


def __reset():
    """Reset all function plugins. For testing only."""

    print("Resetting functions")

    for plugin in list(_FUNCTIONS.values()):
        plugin.deactivate()


def register_core_plugins():
    """Find all the core function plugins and activate them."""

    for cls in CoreFunctionPlugin.__subclasses__():
        obj = cls()
        obj.activate()


class CoreFunctionPlugin(FunctionPlugin):
    """For simpler initialization and location of core function plugins."""

    def __init__(self, name, description, arg_specs):
        super().__init__(name, description, arg_specs,
                         priority=self.PRIO_CORE)

    def func(self, *args):
        """This still must be created by child classes."""
        raise NotImplementedError


class IntPlugin(CoreFunctionPlugin):
    """Convert integer strings to ints of arbitrary bases."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="int",
            description="Convert an integer to .",
            arg_specs={
                'value': str,
                'base': num
            },
        )

    def func(self, value, base):
        """Convert the given string 'value' as an integer of
         the given base. Bases from 2-32 area allowed."""

        return int(value, base)


class RoundPlugin(CoreFunctionPlugin):
    """Round the given number to the nearest integer."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="round",
            description="Round the given number to the nearest integer.",
            arg_specs={'value': float})

    def func(self, val):
        """Round the given number to the nearest int."""

        return round(val)


class FloorPlugin(CoreFunctionPlugin):
    """Get the floor of the given number."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="floor",
            description="Return the integer floor.",
            arg_specs={'value': float})

    def func(self, val):
        """Round the given number to the nearest int."""

        return math.floor(val)


class CeilPlugin(CoreFunctionPlugin):
    """Get the ceiling of the given number."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="ceil",
            description="Return the integer ceiling.",
            arg_specs={'value': float})

    def func(self, val):
        """Round the given number to the nearest int."""

        return math.ceil(val)


class SumPlugin(CoreFunctionPlugin):
    """Get the floating point sum of the given numbers."""

    def __init__(self):
        """Setup plugin."""

        super().__init__(
            name="sum",
            description="Return the sum of the given numbers.",
            arg_specs={'values': [num]})

    def func(self, vals):
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
            arg_specs={'values': [num]},
        )

    def func(self, vals):
        """Get the average of vals. Will always return a float."""

        return sum(vals)/len(vals)


class ListLenPlugin(CoreFunctionPlugin):
    """Return the length of the given list. Unlike python's len, this only
    applies to lists."""

    def __init__(self):
        """Setup plugin"""

        super().__init__(
            name='list_len',
            description='Return the integer length of the given list.',
            arg_specs=None,
        )

    def _validate_arg(self, arg, spec):
        if not isinstance(arg, list):
            raise FunctionPluginError(
                "The list_len function only accepts lists. Got {}"
                .format(arg)
            )
        return arg

    def func(self, list_arg):
        """Just return the length of the list."""

        return len(list_arg)


class RandomPlugin(CoreFunctionPlugin):
    """Return a random number in [0,1)."""

    def __init__(self):
        """Setup Plugin"""

        super().__init__(
            name="random",
            description="Return a random float in [0,1).",
            arg_specs={})

    def func(self):
        """Return a random float in [0,1)."""

        return random.random()
