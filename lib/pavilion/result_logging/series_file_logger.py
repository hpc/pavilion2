from pathlib import Path
import json
from typing import Dict

from pavilion.errors import ResultLoggerPluginError
from .base_classes import ResultLoggerPlugin, ResultLogger


class SeriesFileLoggerFactory(ResultLoggerPlugin):
    """Basic plugin for logging to a separate file for each series. Responsible for generating
    SeriesFileResultLoggers from configs."""

    def __init__(self):
        super().__init__(
            name="series_file",
            description="Log to a separate file for each series",
            priority=self.PRIO_CORE)

    def validate_config(self, config: Dict) -> None:
        plugin_name = config.get("plugin", "")
        dest = config.get("dest")

        if plugin_name != self.name:
            raise ResultLoggerPluginError(
                f"Name {plugin_name} does not match plugin type {self.name}.")

        if dest is None:
            raise ResultLoggerPluginError("No logging destination provided.")

        if not Path(dest).is_absolute():
            raise ResultLoggerPluginError(f"Provided path {dest} is not an absolute path.")

    def _make_logger(self, config: Dict, sid: str) -> "SeriesFileResultLogger":
        dest = Path(config.get("dest")) / f"{sid}.log"

        return SeriesFileResultLogger(dest)


class SeriesFileResultLogger(ResultLogger):
    """Simple result logger for writing results to a file."""

    RESULTS_FN = "results.log"

    def __init__(self, dest: Path):
        self.dest = dest
        self.dest.parent.mkdir(exist_ok=True)

    def log(self, results: Dict) -> None:
        with open(self.dest, "a") as fout:
            json.dump(results, fout)
            fout.write("\n")
