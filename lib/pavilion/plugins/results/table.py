from pavilion import result_parsers
from pavilion import config
import yaml_config as yc
#import numpy as np
import pavilion.test_config
import re


class Table(result_parsers.ResultParser):
    """Find matches to the given regex in the given file. The matched string
    or strings are returned as the result."""

    def __init__(self):
        super().__init__(name='table')

    def get_config_items(self):

        config_items = super().get_config_items()
        config_items.extend([
            yc.ListElem(
                'row_names', sub_elem=yc.StrElem(),
                help_text="Column names"
            ),
            yc.ListElem(
                'col_names', sub_elem=yc.StrElem(),
                help_text="Column names")
        ])

        return config_items

    def _check_args(self, row_names=None, col_names=None):

        if (not row_names) or (not col_names):
            raise result_parsers.ResultParserError(
                "row AND column names required"
            )
        else:
            print("rows: " + str(row_names))
            print("columns: " + str(col_names))

    def __call__(self, test, file, row_names=None, col_names=None):

        table_str = ""
        row_col_names = []
        row_col_names.extend(row_names)
        row_col_names.extend(col_names)
        with open(file.name, 'r'):
            for line in file:
                res = any(ele in str(line) for ele in row_col_names)
                if res is True:
                    table_str = table_str + line
        
        #table_vals = np.genfromtxt(table_str, dtype=str, skip_header=1)

        return table_str
