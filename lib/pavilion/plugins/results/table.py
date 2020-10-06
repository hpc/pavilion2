import re

import pavilion.result.base
import yaml_config as yc
from pavilion.result import parsers


class Table(parsers.ResultParser):

    """Parses tables."""

    def __init__(self):
        super().__init__(
            name='table',
            description="Parses tables",
            config_elems=[
                yc.StrElem(
                    'delimiter',
                    help_text="Delimiter that splits the data."
                ),
                yc.StrElem(
                    'col_num', required=True,
                    help_text="Number of columns in table, including row "
                              "names, if there is such a column."
                ),
                yc.StrElem(
                    'has_header',
                    help_text="Set True if there is a column for row names. "
                              "Will create dictionary of dictionaries."
                ),
                yc.ListElem(
                    'col_names', required=False, sub_elem=yc.StrElem(),
                    help_text="Column names if the user knows what they are."
                ),
                yc.StrElem(
                    'by_column',
                    help_text="Set to True if the user wants to organize the "
                              "nested dictionaries by columns. Default False. "
                              "Only set if `has_header` is True. "
                              "Otherwise, Pavilion will ignore."
                )
            ],
            defaults={
                'delimiter': ' ',
                'has_header': 'False',
                'by_column': 'True',
            },
            validators={
                'has_header': ('True', 'False'),
                'by_column': ('True', 'False'),
                'col_num': int,
            }

        )

    def _check_args(self, **kwargs):

        col_names = kwargs['col_names']

        try:
            if len(col_names) != 0:
                if len(col_names) != kwargs['col_num']:
                    raise pavilion.result.base.ResultError(
                        "Length of `col_names` does not match `col_num`."
                    )
        except ValueError:
            raise pavilion.result.base.ResultError(
                "`col_names` needs to be an integer."
            )

        return kwargs

    def __call__(self, file, delimiter=None, col_num=None,
                 has_header=None, col_names=None, by_column=None):

        match_list = []

        # generate regular expression
        value_regex = r'(\S+| )'
        new_delimiter = r'\s*' + delimiter + r'\s*'
        value_regex_list = []
        for i in range(int(col_num)):
            value_regex_list.append(value_regex)
        str_regex = new_delimiter.join(value_regex_list)
        str_regex = r'^\s*' + str_regex + r'\s*$'

        regex = re.compile(str_regex)
        for line in file.readlines():
            match_list.extend(regex.findall(line))

        # if column names isn't specified, assume column names are the first
        # in the match_list
        if not col_names:
            col_names = match_list[0]

        # table has row names AND column names = dictionary of dictionaries
        if has_header == "True":
            result_dict = {}
            if match_list[0] in col_names:
                match_list = match_list[1:]
            col_names = col_names[1:]
            row_names = [] # assume first element in list is row name
            for m_idx in range(len(match_list)):
                row_names.append(match_list[m_idx][0])
                match_list[m_idx] = match_list[m_idx][1:]
            if row_names[0] is col_names[0]:
                row_names = row_names[1:]
            for col_idx in range(len(col_names)):
                result_dict[col_names[col_idx]] = {}
                for row_idx in range(len(row_names)):
                    result_dict[col_names[col_idx]][row_names[row_idx]] = \
                        match_list[row_idx][col_idx]

            # "flip" the dictionary if by_column is set to False (default)
            if by_column == "False":
                tmp_dict = {}
                for rname in row_names:
                    tmp_dict[rname] = {}
                    for cname in col_names:
                        tmp_dict[rname][cname] = result_dict[cname][rname]
                result_dict = tmp_dict

        # table does not have rows = dictionary of lists
        else:
            result_dict = {}
            for col in range(len(match_list[0])):
                result_dict[match_list[0][col]] = []
                for v_list in match_list[1:]:
                    result_dict[match_list[0][col]].append(v_list[col])

        return result_dict
