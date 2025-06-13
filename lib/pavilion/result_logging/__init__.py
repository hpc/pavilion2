from .base_classes import ResultLoggerPlugin, get_result_loggers
from .series_file_logger import SeriesFileLoggerFactory

_builtin_logging_plugins = [
    SeriesFileLoggerFactory
]

def register_core_plugins():
    for cls in _builtin_logging_plugins:
        cls().activate()

ResultLoggerPlugin.register_core_plugins = register_core_plugins
