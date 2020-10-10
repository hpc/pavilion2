"""Contains the base Expression Function plugin class."""

import inspect
import logging
import re

from yapsy import IPlugin
from .common import FunctionPluginError

LOGGER = logging.getLogger(__file__)

# The dictionary of available function plugins.
_FUNCTIONS = {}  # type: {str,FunctionPlugin}


def num(val):
    """Return val as an int, float, or bool, depending on what it most
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
    """Plugin base class for math functions.

    Child classes must override ``__init__`` (as is typical for Pavilion
    plugin), and must also provide a method to act as the function itself.
    This method must have the same name as the plugin (ie. The 'max' plugin
    must have a 'max' method), and take the arguments the function expects.
    """

    VALID_SPEC_TYPES = (
        int,
        float,
        str,
        bool,
        num,
        None
    )

    NAME_RE = re.compile(r'[a-zA-Z][a-zA-Z0-9_]*$')

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    core = False

    def __init__(self, name, arg_specs, description=None,
                 priority=PRIO_COMMON):
        """
        :param str name: The name of this function.
        :param str description: A short description of this function. The
            class docstring is used by default.
        :param int priority: The plugin priority.
        :param [type] arg_specs: A list of type specs for each function
            argument. The spec for each argument defines what structure
            and types the value will have, and the auto-conversions that
            will happen if possible. ``None`` denotes that arg_specs
            won't be used or validated, and requires that ``_validate_arg`` be
            overridden.
        """

        if not self.NAME_RE.match(name):
            raise FunctionPluginError(
                "Invalid function name: '{}'".format(name))

        self.name = name
        self.priority = priority

        if description is None:
            if self.__doc__ == FunctionPlugin.__doc__:
                raise FunctionPluginError(
                    "A plugin description is required. Either add a doc "
                    "string to the plugin class, or provide a description "
                    "argument to __init__."
                )
            description = ' '.join(self.__doc__.split())
        self.description = description

        sig = inspect.signature(getattr(self, self.name))

        if arg_specs is None:
            if self._validate_arg is FunctionPlugin._validate_arg:
                raise RuntimeError(
                    "Function plugin {} at {} was given an arg_spec of "
                    "'None', but did not override '_validate_arg'."
                    .format(self.name, self.path)
                )
            if self.__class__.signature is FunctionPlugin.signature:
                raise RuntimeError(
                    "Function plugin {} at {} was given an arg_spec of "
                    "'None', but did not override 'signature'."
                    .format(self.name, self.path)
                )
        else:
            if len(sig.parameters) != len(arg_specs):
                raise FunctionPluginError(
                    "Invalid arg specs. The function takes {} arguments, but"
                    "an arg_spec of length {} was provided."
                    .format(len(sig.parameters), len(arg_specs)))

            for arg_spec in arg_specs:
                self._validate_arg_spec(arg_spec)

        self.arg_specs = arg_specs

        super().__init__()

    def _validate_arg_spec(self, arg):
        """Recursively validate the argument spec, to make sure plugin
        creators are using this right.
        :param arg: A valid arg spec is a structure of lists and
            dicts, and types from self.VALID_SPEC_TYPES.

            - Lists should contain one representative containing type.
            - Dicts should have at least one key-value pair (with string keys).
            - Dict specs don't have to contain every key the dict might have,
              just those that will be used.
            - Specs may be any structure of these types, as long
              as they comply with the above rules.
            - The 'num' spec type will accept strings, floats, ints,
              or bool. ints and floats are left alone, bools become
              ints, and strings become an int or a float if they can.
            - 'None' may be given as the type of contained items for lists
              or dicts, denoting that contained time doesn't matter.
        :raises FunctionPluginError: On a bad arg spec.
        """

        if isinstance(arg, list):
            if len(arg) != 1:
                raise FunctionPluginError(
                    "Invalid list spec argument. List arguments must contain "
                    "a single subtype. This had '{}'."
                    .format(arg)
                )
            self._validate_arg_spec(arg[0])

        elif isinstance(arg, dict):
            if len(arg) == 0:
                raise FunctionPluginError(
                    "Invalid dict spec argument. Dict arguments must contain "
                    "at least one key-value pair. This had '{}'."
                    .format(arg)
                )
            for key, sub_arg in arg.items():
                self._validate_arg_spec(sub_arg)

        elif arg is None:
            # We don't care what the argument type is
            pass

        elif arg not in self.VALID_SPEC_TYPES:
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
                    "Invalid number of arguments defined for function {}. Got "
                    "{}, but expected {}"
                    .format(self.name, len(args), len(self.arg_specs)))

            # Create the full list of validated arguments.
            val_args = []
            for arg, spec in zip(args, self.arg_specs):
                val_args.append(self._validate_arg(arg, spec))
        else:
            val_args = args

        try:
            func = getattr(self, self.name)
            return func(*val_args)
        except Exception as err:
            raise FunctionPluginError(
                "Error in function plugin {}: {}"
                .format(self.name, err)
            )

    @property
    def signature(self):
        """Generate a function signature for this function.
        :newlines: Put each argument on a separate line.
        """

        sig = inspect.signature(getattr(self, self.name))
        arg_names = list(sig.parameters.keys())

        parts = [self.name + '(']
        arg_parts = []
        for i in range(len(arg_names)):
            arg_name = arg_names[i]
            spec = self.arg_specs[i]
            arg_parts.append(
                '{}: {}'.format(arg_name, self._spec_to_desc(spec)))

        parts.append(', '.join(arg_parts))
        parts.append(')')

        return ''.join(parts)

    @property
    def long_description(self):
        """Return the docstring for the function."""

        func = getattr(self, self.name)
        desc = func.__doc__

        return ' '.join(desc.split())

    def _spec_to_desc(self, spec):
        """Convert an argument spec into a descriptive structure that
        can be reasonably printed."""

        if isinstance(spec, list):
            return [self._spec_to_desc(spec[0])]
        elif isinstance(spec, dict):
            return {k: self._spec_to_desc(v) for k, v in spec.items()}
        elif spec is None:
            return 'Any'
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

        if spec is None:
            # None denotes to leave the argument alone.
            return arg

        try:
            # Boolean strings need a little conversion help when
            # converting to other types. The num type takes care of this
            # internally.
            if spec in (int, float) and arg in ('True', 'False'):
                arg = bool(arg)

            return spec(arg)
        except ValueError:
            raise FunctionPluginError(
                "Invalid {} ({})"
                .format(spec.__name__, arg))

    def activate(self):
        """Yapsy runs this when adding the plugin. Add our plugin
        to the registry of function plugins."""

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


def __reset():
    """Reset all function plugins. For testing only."""

    for plugin in list(_FUNCTIONS.values()):
        plugin.deactivate()
