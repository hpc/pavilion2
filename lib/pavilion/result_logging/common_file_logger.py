from pathlib import Path
import json
import io
from typing import Dict, Optional, TextIO

from pavilion import output
from pavilion.errors import ResultLoggerPluginError
from pavilion.lockfile import FuzzyLock
from .base_classes import ResultLoggerPlugin, ResultLogger


class CommonFileLoggerFactory(ResultLoggerPlugin):
    """Basic plugin for logging to a single common file. Responsible for generating
    SeriesFileResultLoggers from configs."""

    def __init__(self):
        super().__init__(
            name="common_file",
            description="Log to a file common among all series.",
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
                     outfile: Optional[TextIO] = None) -> "CommonFileResultLogger":
        dest = Path(config.get("dest"))

        return CommonFileResultLogger(dest, outfile)


class CommonFileResultLogger(ResultLogger):
    """Simple result logger for writing results to a file."""

    RESULTS_FN = "results.log"

    def __init__(self, dest: Path, outfile: Optional[TextIO] = None):
        self.dest = dest

        if self.dest.is_dir():
            self.dest /= RESULTS_FN

        self.outfile = outfile or io.StringIO()

    def log(self, results: Dict) -> None:
        output.fprint(self.outfile, f"{type(self).__name__}: Logging {results} to {self.dest}...")

        with FuzzyLock(self.dest.parent / "results.lock", timeout=10):
            with open(self.dest, "a") as fout:
                json.dump(results, fout)
                fout.write("\n")
