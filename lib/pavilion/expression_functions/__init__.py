"""Expression Functions are plugins that define the functions that can be
used in Pavilion expressions, both within normal Pavilion strings and
in result evaluations.
"""

from .base import (FunctionPlugin, _FUNCTIONS, num, __reset)
from .common import FunctionPluginError, FunctionArgError
from .core import CoreFunctionPlugin


def get_plugin(name: str) -> FunctionPlugin:
    """Get the function plugin called 'name'."""

    if name not in _FUNCTIONS:
        raise FunctionPluginError("No such function '{}'".format(name))
    else:
        return _FUNCTIONS[name]

def list_plugins():
    """Return the list of function plugin names."""

    return _FUNCTIONS.keys()


def register_core_plugins():
    """Find all the core function plugins and activate them."""

    for cls in CoreFunctionPlugin.__subclasses__():
        obj = cls()
        obj.activate()


FunctionPlugin.register_core = register_core_plugins
