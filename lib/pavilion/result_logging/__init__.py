from .base_classes import ResultLoggerPlugin, get_result_loggers, get_result_dests
from .file_logger import FileLoggerFactory

_builtin_logging_plugins = [
    FileLoggerFactory
]

def register_core_plugins():
    for cls in _builtin_logging_plugins:
        cls().activate()

ResultLoggerPlugin.register_core_plugins = register_core_plugins
