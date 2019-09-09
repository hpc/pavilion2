from pavilion import result_parsers
import yaml_config as yc
import re
from pavilion.utils import dbg_print

class Table(result_parsers.ResultParser):

    """Parses tables."""

    def __init__(self):
        super().__init__(
            name='table',
            description="Parses tables"
        )

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.StrElem(
                'delimiter', required=True,
                help_text="Constant that will be placed in result."
            ),
            yc.StrElem(
                'col_num', required=True,
                help_text="Number of columns in table."
            )
        ])

        return config_items

    def _check_args(self, delimiter=None, col_num=None):
        
        if delimiter == "":
            raise result_parsers.ResultParserError(
                "Delimiter required."
        )

    def __call__(self, test, file, delimiter=None, col_num=None):

        match_list = []

        # generate regular expression
        value_regex = '(.+| )'
        value_regex_list = []
        for i in range(int(col_num)):
            value_regex_list.append(value_regex)
        str_regex = delimiter.join(value_regex_list)

        regex = re.compile(str_regex)
        for line in file.readlines():
            match_list.extend(regex.findall(line))

        return match_list
