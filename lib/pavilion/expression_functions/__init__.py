"""Expression Functions are plugins that define the functions that can be
used in Pavilion expressions, both within normal Pavilion strings and
in result evaluations.
"""

from typing import Optional

from .base import (FunctionPlugin, _FUNCTIONS, num, __reset)
from .core import CoreFunctionPlugin
from ..errors import FunctionPluginError


def get_plugin(name: str) -> Optional[FunctionPlugin]:
    """Get the function plugin called 'name'. Returns None if a plugin with the given name
    does not exist."""

    return _FUNCTIONS.get(name)

def list_plugins():
    """Return the list of function plugin names."""

    return _FUNCTIONS.keys()

def register_core_plugins():
    """Find all the core function plugins and activate them."""

    for cls in CoreFunctionPlugin.__subclasses__():
        obj = cls()
        obj.activate()


FunctionPlugin.register_core_plugins = register_core_plugins
