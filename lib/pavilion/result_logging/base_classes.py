import re
import logging
import inspect
import io
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Set, Optional, TextIO

from yapsy import IPlugin

from pavilion import output
from pavilion.errors import ResultLoggerPluginError
from pavilion.micro import set_default


LOGGER = logging.getLogger(__file__)


_RESULT_LOGGER_PLUGINS = {}


def get_plugin(name: str) -> Optional["ResultOutputPlugin"]:
    """Get the result output plugin wth the specified name."""

    return _RESULT_LOGGER_PLUGINS.get(name)


def get_result_loggers(pav_cfg: "PavConfig",
                       sid: str,
                       outfile: Optional[TextIO] = None,
                       errfile: Optional[TextIO] = None) -> Set["ResultLogger"]:
    """Get all result logger instances defined in the given Pavilion config."""

    loggers = set()

    for log_config in pav_cfg.get("result_loggers"):
        plugin_name = log_config.get("plugin", "")
        factory = get_plugin(plugin_name)

        if factory is None:
            raise ResultLoggerPluginError(
                f"No result logger plugin found with name '{plugin_name}'")

        loggers.add(factory.make_logger(log_config, sid, outfile))

    return loggers


def __reset() -> None:
    global _RESULT_LOGGER_PLUGINS

    _RESULT_LOGGER_PLUGINS = {}


class ResultLoggerPlugin(IPlugin.IPlugin, ABC):

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self, name: str, description: str, priority: int = PRIO_COMMON):
        super().__init__()

        if self.NAME_VERS_RE.match(name) is None:
            raise LoggingPluginError(
                "Invalid module name: '{}'"
                .format(name))

        self.name = name
        self.help_text = description
        self.priority = priority
        self.path = inspect.getfile(self.__class__)

    @abstractmethod
    def validate_config(self, config: Dict) -> None:
        """Validate the result logger config."""

    @abstractmethod
    def _make_logger(self,
                     config: Dict,
                     sid: str,
                     outfile: Optional[TextIO] = None) -> "ResultLogger":
        """Create the result logger from the given config and series ID."""

    def make_logger(self,
                    config: Dict,
                    sid: str,
                    outfile: Optional[TextIO] = None) -> "ResultLogger":
        """Validate the config and create the result logger."""

        self.validate_config(config)

        return self._make_logger(config, sid, outfile=outfile)

    def activate(self):
        """Add this plugin to the result output plugin list."""

        if self.name in _RESULT_LOGGER_PLUGINS:
            other = _RESULT_LOGGER_PLUGINS[self.name]
            if self.priority > other.priority:
                LOGGER.info(
                    "Result output plugin '%s' at %s is superseded by %s.",
                    self.name, other.path, self.path)
                _RESULT_LOGGER_PLUGINS[self.name] = self
            elif self.priority < other.priority:
                LOGGER.info(
                    "Result output plugin '%s' at %s is ignored in lieu of %s.",
                    self.name, self.path, other.path)
            else:
                raise RuntimeError("Result output plugin conflict. Plugin '{}' at {} "
                                   "has the same priority as {}"
                                   .format(self.name, other.path, self.path))
        else:
            _RESULT_LOGGER_PLUGINS[self.name] = self

    def deactivate(self):
        """Remove this plugin from the logging plugin list."""

        del _RESULT_LOGGER_PLUGINS[self.name]

    def __repr__(self):
        return '<{} from file {} named {}, priority {}>'.format(
            self.__class__.__name__,
            self.path,
            self.name,
            self.priority
        )

class ResultLogger(ABC):
    """Abstract base class for all result loggers."""

    def __init__(self, name: Optional[str] = None,
                 outfile: Optional[TextIO] = None, errfile: Optional[TextIO] = None):

        self.outfile = outfile
        # If no separate errfile is specified, just use the outfile
        self.errfile = set_default(errfile, outfile)

        self.outfile = self.outfile or io.StringIO()
        self.errfile = self.errfile or io.StringIO()

        self.name = set_default(name, type(self).__name__)

    def log(self, results: Dict) -> None:
        """Log a test's results dictionary."""

        output.fprint(self.outfile, self.get_log_message(results))

        try:
            self._log(results)
        except ResultLoggerPluginError as err:
            output.fprint(self.errfile,
                          f"{self.name}: Error logging results: {err}.",
                          color=output.RED)

    @abstractmethod
    def _log(self, results: Dict) -> None:
        pass

    @abstractmethod
    def get_log_message(self, results: Dict) -> str:
        """Get the log message to print to the results logging log."""

    def __call__(self, results: Dict) -> None:
        self.log(results)
