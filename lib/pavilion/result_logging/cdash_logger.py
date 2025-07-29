from io import BytesIO
import xml.etree.ElementTree as ET
from typing import Dict

import requests

from pavilion.errors import ResultLoggerPluginError
from .base_classes import ResultLoggerPlugin, ResultLogger


class CDashLoggerFactory(ResultLoggerPlugin):
    """Plugin for logging to CDash. Responsible for generating CDashResultLoggers from configs."""

    def __init__(self):
        super().__init__(
            name="cdash",
            description="Log to a separate file for each series",
            priority=self.PRIO_CORE)

    def validate_config(self, config: Dict) -> None:
        plugin_name = config.get("plugin", "")
        endpoint = config.get("endpoint")

        if plugin_name != self.name:
            raise ResultLoggerPluginError(
                f"Name {plugin_name} does not match plugin type {self.name}.")

        if dest is None:
            raise ResultLoggerPluginError("No CDash endpoint provided.")

    def _make_logger(self, config: Dict, sid: str) -> "SeriesFileResultLogger":
        return CDashResultLogger(config.get("endpoint"))


class CDashResultLogger(ResultLogger):
    """Result logger for logging results to a CDash instance."""

    def __init__(self, endpoint: str, proj_name: str):
        self.endpoint = endpoint
        self.proj_name = proj_name


    def as_xml(results: Dict) -> BytesIO:
        """Convert the results dictionary into an XML document for consumption
        by CDash."""

        site = ET.Element("Site")
        testing = ET.SubElement(site, "Testing")
        test = ET.SubElement(testing, "Test", Status=results.get("result"))
        name = ET.SubElement(test, "Name")
        name.text = results.get("name")

        tree = ET.ElementTree(site)

        buffer = io.BytesIO()
        tree.write(buffer, encoding="UTF-8", xml_declaration=True)

        return buffer.getvalue()


    def log(self, results: Dict) -> None:
        # 1. Convert results to XML
        test_xml = self.xml(results)

        # 2. Submit results to CDash endpoint
        response = requests.post(
                        self.endpoint,
                        params={"project": self.proj_name, "FileName": "Test.xml"},
                        data=test_xml,
                        headers={"Content-Type": "application/xml"}
                        )
