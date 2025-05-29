from .base_classes import ResultOutputPlugin, get_plugin
from .files import Files

_builtin_logging_plugins = [
    Files
]

def register_core_plugins():
    for cls in _builtin_logging_plugins:
        cls().activate()

ResultOutputPlugin.register_core_plugins = register_core_plugins