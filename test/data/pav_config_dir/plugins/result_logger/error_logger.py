from pavilion.result_logging import ResultLoggerPlugin, ResultLogger
from pavilion.errors import ResultLoggerPluginError

from typing import Dict, Optional, TextIO


class ErrorResultLoggerFactory(ResultLoggerPlugin):
    def __init__(self):
        super().__init__(
            name="error_logger",
            description="Deliberately raises an error when logging results.",
            priority=self.PRIO_CORE)

    def validate_config(self, config: Dict) -> None:
        plugin_name = config.get("plugin", "")

        if plugin_name != self.name:
            raise ResultLoggerPluginError(
                f"Name {plugin_name} does not match plugin type {self.name}.")

    # pylint: disable=arguments-renamed
    def _make_logger(self,
                     config: Dict,
                     sid: str,
                     name: Optional[str] = None,
                     outfile: Optional[TextIO] = None,
                     errfile: Optional[TextIO] = None) -> "ErrorResultLogger":

        return ErrorResultLogger(name, outfile, errfile)

class ErrorResultLogger(ResultLogger):
    def _log(self, results: Dict) -> None:
        raise ResultLoggerPluginError("This error was raised deliberately by the ErrorResultLogger.")

    def get_log_message(self, results: Dict) -> str:
        return f"{self.name}: Logging {results}..."