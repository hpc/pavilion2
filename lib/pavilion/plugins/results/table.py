from pavilion.result import parsers

import pavilion.result.base
import yaml_config as yc
import re
import copy


class Table(parsers.ResultParser):

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
                'delimiter', default=' ',
                help_text="Delimiter that splits the data."
            ),
            yc.StrElem(
                'col_num', required=True,
                help_text="Number of columns in table, including row names, "
                          "if there is such a column."
            ),
            yc.StrElem(
                'has_header', default='False', choices=['True', 'False'],
                help_text="Set True if there is a column for row names. Will "
                          "create dictionary of dictionaries."
            ),
            yc.ListElem(
                'col_names', required=False, sub_elem=yc.StrElem(),
                help_text="Column names if the user knows what they are."
            ),
            yc.StrElem(
                'by_column', choices=['True', 'False'], default='True',
                help_text="Set to True if the user wants to organize the "
                          "nested dictionaries by columns. Default False. "
                          "Only set if `has_header` is True. "
                          "Otherwise, Pavilion will ignore."
            ),
            yc.StrElem(
                'start_re',
                help_text="Partial regex of the start of the table. "
            ),
            yc.StrElem(
                'row_num',
                help_text="Number of row numbers, including column names."
            ),
            yc.StrElem(
                'start_skip',
                help_text="Number of lines between `start_re` and actual table. "
                          "Only set if `start_re` is also set."
            )
        ])

        return config_items

    def _check_args(self, delimiter=None, col_num=None, has_header=None,
                    col_names=[], by_column=True, start_re=None,
                    row_num=None, start_skip=None):

        try:
            if len(col_names) is not 0:
                if len(col_names) != int(col_num):
                    raise pavilion.result.base.ResultError(
                        "Length of `col_names` does not match `col_num`."
                    )
        except ValueError:
            raise pavilion.result.base.ResultError(
                "`col_names` needs to be an integer."
            )
        try:
            int(start_skip)
            int(row_num)
            int(col_num)
        except ValueError:
            raise pavilion.result.base.ResultError(
                "num_skip, col_num, and row_num need to be integers"
            )

    def __call__(self, test, file, delimiter=None, col_num=None,
                 has_header='', col_names=[], by_column=True, 
                 start_re=None, row_num=None, start_skip=None):

        match_list = []
        lines = file.readlines()
        new_lines = []
        for line_index in range(len(lines)):
            if start_re in lines[line_index]:
                new_lines = lines[line_index:]

        if not new_lines:
            raise result_parsers.ResultParserError(
                "`start_re` not found in file."
            )

        if start_skip:
            del new_lines[1:1+int(start_skip)]

        if row_num:
            new_lines = new_lines[1:int(row_num)+1]

        # generate regular expression
        value_regex = '(\S+| )'
        new_delimiter = '\s*' + delimiter + '\s*'
        value_regex_list = []
        for i in range(int(col_num)):
            value_regex_list.append(value_regex)
        str_regex = new_delimiter.join(value_regex_list)
        str_regex = '^\s*' + str_regex + '\s*$'

        regex = re.compile(str_regex)
        for line in new_lines:
            match_list.extend(regex.findall(line))

        # if column names isn't specified, assume column names are the first
        # in the match_list
        if not col_names:
            col_names = match_list[0]

        # fix naming conflicts in column names list if necessary
        if len(set(col_names)) != len(col_names):
            temp_col_names = []
            name_tally = {}

            for name in col_names:
                name_tally[name] = 0

            for name in col_names:
                name_tally[name] = name_tally[name] + 1
                if name not in temp_col_names:
                    temp_col_names.append(name)
                else:
                    new_name = name + str(name_tally[name])
                    temp_col_names.append(new_name)

            col_names = temp_col_names

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
