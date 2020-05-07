"""Expression Functions are plugins that define the functions that can be
used in Pavilion expressions, both within normal Pavilion strings and
in result analysis strings.
"""

from .base import (FunctionPlugin, FunctionPluginError, FunctionArgError,
                   CoreFunctionPlugin, _FUNCTIONS, num, __reset,
                   register_core_plugins)


def get_plugin(name: str) -> FunctionPlugin:
    """Get the function plugin called 'name'."""

    if name not in _FUNCTIONS:
        raise FunctionPluginError("No such function '{}'".format(name))
    else:
        return _FUNCTIONS[name]
