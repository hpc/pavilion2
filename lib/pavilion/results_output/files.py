from pathlib import Path
from typing import Dict

from pavilion.errors import LoggingPluginError
from .base_classes import ResultOutputPlugin

class Files(ResultOutputPlugin):
    """Basic plugin for logging to a file."""

    RESULTS_FN = "results.log"

    def __init__(self):
        super().__init__(
            name="files",
            description="Log to a file",
            priority=self.PRIO_CORE)
    
    def validate_config(self, config: Dict) -> None:
        plugin_name = config.get("plugin", "")
        dest = config.get("dest")

        if plugin_name != self.name:
            raise LoggingPluginError(f"Name {plugin_name} does not match plugin type {self.name}.")
        
        if dest is None:
            raise LoggingPluginError("No logging destination provided.")
        
        if not Path(dest).is_absolute():
            raise LoggingPluginError(f"Provided path {dest} is not an absolute path.")
    
    def log_results(self, config: Dict, results: Dict) -> None:
        dest = Path(config.get("dest"))
        
        if dest.is_dir():
            dest = dest / self.RESULTS_FN

        with open(dest):
            dest.write(results)