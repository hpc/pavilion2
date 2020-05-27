"""Expression Functions are plugins that define the functions that can be
used in Pavilion expressions, both within normal Pavilion strings and
in result evaluations.
"""

from .base import (FunctionPlugin, _FUNCTIONS, num, __reset)
from .common import FunctionPluginError, FunctionArgError
from .core import register_core_plugins, CoreFunctionPlugin


def get_plugin(name: str) -> FunctionPlugin:
    """Get the function plugin called 'name'."""

    if name not in _FUNCTIONS:
        raise FunctionPluginError("No such function '{}'".format(name))
    else:
        return _FUNCTIONS[name]
