from pavilion import result_parsers
from pavilion.utils import dbg_print
import yaml_config as yc
import re
import json

class Jsonrp(result_parsers.ResultParser):
    """Converts JSON output into dictionary."""

    def __init__(self):
        super().__init__(
            name='jsonrp',
            description="Converts JSON output into dictionary.")

    def get_config_items(self):

        config_items = super().get_config_items()

        return config_items

    def _check_args(self, const=None):

        return

    def __call__(self, test, file):

        # Effectively reads contents of file into single string
        contents = file.read()

        # Pulls the first JSON block from the file
        try:
            json_block = re.search(r'{(.|\s)*}', contents)
            json_block = json_block.group(0)

        except AttributeError as err:
            return {}

        # Loads the JSON as a dictionary
        try:
            json_dict = json.loads(json_block)

        except ValueError as err:
            return {}

        return json_dict
