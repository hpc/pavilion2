from pavilion.result_logging import ResultLoggerPlugin, ResultLogger

from typing import Dict, Optional, TextIO


class NullResultLoggerFactory(ResultLoggerPlugin):
    def __init__(self):
        super().__init__(
            name="null_logger",
            description="Result logger that does nothing.",
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
                     errfile: Optional[TextIO] = None) -> "NullResultLogger":

        return NullResultLogger(name, outfile, errfile)

class NullResultLogger(ResultLogger):
    def _log(self, results: Dict) -> None:
        pass

    def get_log_message(self, results: Dict) -> str:
        return f"{self.name}: Logging {results}..."