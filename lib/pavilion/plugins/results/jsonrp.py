from pavilion import result_parsers
from pavilion.utils import dbg_print
import yaml_config as yc
import re
import json

class Jsonrp(result_parsers.ResultParser):
    """Converts JSON output into dictionary/list and places it in the
    RESULTS.json file at the given key."""

    def __init__(self):
        super().__init__(
            name='jsonrp',
            description="Converts JSON output into dictionary/list and places "
            "it in the RESULTS.json file at the given key.")

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'regex', default="",
                help_text="The regex to use to find the line before the JSON "
                "block in the given file. If nothing is provided it is assumed "
                "the JSON block is the first thing in the file. "
            )
        ])

        return config_items

    def _check_args(self, regex=None):

        try:
            re.compile(regex)
        except (ValueError, sre_constants.error) as err:
            raise result_parsers.ResultParserError(
                "Invalid regular expression: {}".format(err))

        type in ['list', 'dictionary']

    def __call__(self, test, file, regex=None):

        decoder = json.JSONDecoder()

        if regex:
            regex = re.compile(regex)
            found = False
            rest_of_file = ""
            for line in file.readlines():
                if not found and regex.search(line):
                    found = True
                elif found:
                    rest_of_file = rest_of_file + line

            try:
                result, index = decoder.raw_decode(rest_of_file)
            except:
                raise result_parsers.ResultParserError("Could not parse json.")

        else:
            try:
                result, index = decoder.raw_decode(file.read())
            except:
                raise result_parsers.ResultParserError("Could not parse json.")

        return result

