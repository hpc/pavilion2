import re
from typing import Dict

from yapsy import IPlugin

from pavilion.errors import LoggingPluginError


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
        """Add this plugin to the logger plugin list."""
        pass

    def deactivate(self):
        """Remove this plugin from the logging plugin list."""
        pass

    def __repr__(self):
        return '<{} from file {} named {}, priority {}>'.format(
            self.__class__.__name__,
            self.path,
            self.name,
            self.priority
        )
