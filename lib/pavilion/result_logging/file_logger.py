from pathlib import Path
from typing import Dict

from pavilion.errors import ResultLoggerPluginError
from .base_classes import ResultLoggerPlugin, ResultLogger


class FileLoggerFactory(ResultLoggerPlugin):
    """Basic plugin for logging to a file. Responsible for generating FileResultLoggers from
    configs."""

    def __init__(self):
        super().__init__(
            name="files",
            description="Log to a file",
            priority=self.PRIO_CORE)
    
    def validate_config(self, config: Dict) -> None:
        plugin_name = config.get("plugin", "")
        dest = config.get("dest")

        if plugin_name != self.name:
            raise ResultLoggerPluginError(f"Name {plugin_name} does not match plugin type {self.name}.")
        
        if dest is None:
            raise ResultLoggerPluginError("No logging destination provided.")
        
        if not Path(dest).is_absolute():
            raise ResultLoggerPluginError(f"Provided path {dest} is not an absolute path.")

    def _make_logger(self, config: Dict) -> "FileResultLogger":
        dest = Path(config.get("dest"))

        return FileResultLogger(dest)


class FileResultLogger(ResultLogger):
    """Simple result logger for writing results to a file."""

    RESULTS_FN = "results.log"

    def __init__(self, dest: Path):
        self.dest = dest

        if self.dest.is_dir():
            self.dest /= RESULTS_FN

    def log(results: Dict) -> None:
        with open(dest) as fout:
            json.dump(results, fout)
