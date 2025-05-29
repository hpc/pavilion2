import re
from typing import Dict

from yapsy import IPlugin

from pavilion.errors import LoggingPluginError


LOGGER = logging.getLogger(__file__)


_OUTPUT_PLUGINS = {}


def get_plugin(name: str) -> "ResultOutputPlugin":
    """Get the result output plugin with the specified name."""

    return _OUTPUT_PLUGINS[name]


class ResultOutputPlugin(IPlugin.IPlugin):

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self, name: str, description: str, priority=PRIO_COMMON):
        super().__init__()

        if self.NAME_VERS_RE.match(name) is None:
            raise LoggingPluginError(
                "Invalid module name: '{}'"
                .format(name))
        
        self.name = name
        self.help_text = description
        self.priority = priority
    
    def validate_config(self, config: Dict) -> None:
        raise NotImplementedError

    def log_results(self, config: Dict, results: Dict) -> None:
        raise NotImplementedError
    
    def activate(self):
        """Add this plugin to the result output plugin list."""

        if self.name in _OUTPUT_PLUGINS:
            other = _OUTPUT_PLUGINS[self.name]
            if self.priority > other.priority:
                LOGGER.info(
                    "Result output plugin '%s' at %s is superseded by %s.",
                    self.name, other.path, self.path)
                _OUTPUT_PLUGINS[self.name] = self
            elif self.priority < other.priority:
                LOGGER.info(
                    "Result output plugin '%s' at %s is ignored in lieu of %s.",
                    self.name, self.path, other.path)
            else:
                raise RuntimeError("Result output plugin conflict. Plugin '{}' at {} "
                                   "has the same priority as {}"
                                   .format(self.name, other.path, self.path))
        else:
            _OUTPUT_PLUGINS[self.name] = self

    def deactivate(self):
        """Remove this plugin from the logging plugin list."""
        
        del _OUTPUT_PLUGINS[self.name]

    def __repr__(self):
        return '<{} from file {} named {}, priority {}>'.format(
            self.__class__.__name__,
            self.path,
            self.name,
            self.priority
        )
