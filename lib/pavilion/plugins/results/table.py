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
                help_text="Number of columns in table, including row names, "
                          "if there is such a column."
            ),
            yc.StrElem(
                'row_col', default='False',
                help_text="Set True if there is a column for row names."
            )
        ])

        return config_items

    def _check_args(self, delimiter=None, col_num=None, row_col=None):
        
        if delimiter == "":
            raise result_parsers.ResultParserError(
                "Delimiter required."
        )

    def __call__(self, test, file, delimiter=None, col_num=None, row_col=None):

        match_list = []

        # generate regular expression
        value_regex = '(\S+| )'
        new_delimiter = ' *' + delimiter + ' *'
        value_regex_list = []
        for i in range(int(col_num)):
            value_regex_list.append(value_regex)
        str_regex = new_delimiter.join(value_regex_list)
        str_regex = '^ *' + str_regex + ' *$'

        regex = re.compile(str_regex)
        for line in file.readlines():
            match_list.extend(regex.findall(line))

        # assume first list in match_list is the column row
        result_dict = {}
        for col in range(len(match_list[0])):
            result_dict[match_list[0][col]] = []
            for v_list in match_list[1:]:
                result_dict[match_list[0][col]].append(v_list[col])

        return result_dict
