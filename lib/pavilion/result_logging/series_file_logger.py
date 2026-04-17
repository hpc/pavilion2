from pathlib import Path
import io
from datetime import datetime
from typing import Dict, Optional, TextIO

from pavilion.output import json_dump
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

    # pylint: disable=arguments-renamed
    def _make_logger(self,
                     config: Dict,
                     sid: str,
                     name: Optional[str] = None,
                     outfile: Optional[TextIO] = None,
                     errfile: Optional[TextIO] = None) -> "SeriesFileResultLogger":

        dest = Path(config.get("dest")) / f"{sid}-{datetime.now().isoformat()}.log"

        return SeriesFileResultLogger(dest, outfile, errfile)


class SeriesFileResultLogger(ResultLogger):
    """Result logger for logging each series to a separate file."""

    def __init__(self, dest: Path, name: Optional[str] = None,
                 outfile: Optional[TextIO] = None, errfile: Optional[TextIO] = None):
        super().__init__(name, outfile, errfile)
        self.dest = dest
        self.dest.parent.mkdir(exist_ok=True)

    def _log(self, results: Dict) -> None:
        """Log a test's results dictionary."""

        try:
            with open(self.dest, "a") as fout:
                json_dump(results, fout)
                fout.write("\n")
        except OSError as err:
            raise ResultLoggerPluginError(f"Error writing to {self.dest}: {err}")
        except TypeError:
            raise ResultLoggerPluginError(f"Error serializing results as JSON: {err}")

    def get_log_message(self, results: Dict) -> str:
        return f"{self.name}: Logging {results} to {self.dest}..."
