from pathlib import Path
import json
import io
from typing import Dict, Optional, TextIO

from pavilion import output
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

    def _make_logger(self,
                     config: Dict,
                     sid: str,
                     outfile: Optional[TextIO] = None) -> "SeriesFileResultLogger":
        dest = Path(config.get("dest")) / f"{sid}.log"

        return SeriesFileResultLogger(dest, outfile)


class SeriesFileResultLogger(ResultLogger):
    """Simple result logger for writing results to a file."""

    RESULTS_FN = "results.log"

    def __init__(self, dest: Path, outfile: Optional[TextIO] = None):
        self.dest = dest
        self.dest.parent.mkdir(exist_ok=True)
        self.outfile = outfile or io.StringIO()

    def log(self, results: Dict) -> None:
        output.fprint(self.outfile, f"{type(self).__name__}: Logging {results} to {self.dest}...")

        with open(self.dest, "a") as fout:
            json.dump(results, fout)
            fout.write("\n")
