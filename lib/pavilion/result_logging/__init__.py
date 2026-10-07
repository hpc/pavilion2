from .base_classes import ResultLogger, ResultLoggerPlugin, get_result_loggers
from .series_file_logger import SeriesFileLoggerFactory
from .common_file_logger import CommonFileLoggerFactory
from .rabbitmq_logger import RabbitMQLoggerFactory

_builtin_logging_plugins = [
    SeriesFileLoggerFactory,
    CommonFileLoggerFactory,
    RabbitMQLoggerFactory,
]


def register_core_plugins():
    for cls in _builtin_logging_plugins:
        cls().activate()


ResultLoggerPlugin.register_core_plugins = register_core_plugins  # type: ignore[attr-defined]
