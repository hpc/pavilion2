from pathlib import Path
import json
import io
from typing import Dict, Optional, TextIO

from pavilion.output import json_dump
from pavilion.errors import ResultLoggerPluginError
from .base_classes import ResultLoggerPlugin, ResultLogger

from flufl.lock import Lock, LockError


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

    # pylint: disable=arguments-renamed
    def _make_logger(self,
                     config: Dict,
                     sid: str,
                     name: Optional[str] = None,
                     outfile: Optional[TextIO] = None,
                     errfile: Optional[TextIO] = None) -> "CommonFileResultLogger":
        dest = Path(config.get("dest"))

        return CommonFileResultLogger(dest, name, outfile, errfile)


class CommonFileResultLogger(ResultLogger):
    """Simple result logger for writing results to a file."""

    RESULTS_FN = "results.log"

    def __init__(self, dest: Path, name: Optional[str] = None,
                 outfile: Optional[TextIO] = None, errfile: Optional[TextIO] = None):
        super().__init__(name, outfile, errfile)
        self.dest = dest

        if self.dest.is_dir():
            self.dest /= RESULTS_FN

        self.outfile = outfile or io.StringIO()

    def _log(self, results: Dict) -> None:
        try:
            with Lock(self.dest.parent / "results.lock", default_timeout=10, lifetime=3):
                with open(self.dest, "a") as fout:
                    json_dump(results, fout)
                    fout.write("\n")
        except TimeoutError:
            raise ResultLoggerPluginError(f"Timed out waiting to acquire lock for {self.dest}.")
        except LockError as err:
            raise ResultLoggerPluginError(f"Error acquiring or releasing lock: {err}.")
        except OSError as err:
            raise ResultLoggerPluginError(f"Error writing to {self.dest}: {err}")
        except TypeError:
            raise ResultLoggerPluginError(f"Error serializing results as JSON: {err}")

    def get_log_message(self, results: Dict) -> str:
        return f"{self.name}: Logging {results} to {self.dest}..."
