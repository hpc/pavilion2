from .base_classes import ResultLoggerPlugin, get_result_loggers
from .series_file_logger import SeriesFileLoggerFactory
from .common_file_logger import CommonFileLoggerFactory
from .cdash_logger import CDashLoggerFactory

_builtin_logging_plugins = [
    SeriesFileLoggerFactory,
    CommonFileLoggerFactory,
    CDashLoggerFactory
]

def register_core_plugins():
    for cls in _builtin_logging_plugins:
        cls().activate()

ResultLoggerPlugin.register_core_plugins = register_core_plugins
