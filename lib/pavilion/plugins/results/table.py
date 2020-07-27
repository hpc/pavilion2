import re
import copy

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
                ),
                yc.StrElem(
                    'start_re',
                    help_text="Partial regex of the start of the table. "
                ),
                yc.StrElem(
                    'nth_start_re',
                    help_text="Nth start_re to consider. Default first "
                              "occurence (0th). "
                ),
                yc.StrElem(
                    'row_num',
                    help_text="Number of row numbers, including column names."
                ),
                yc.StrElem(
                    'start_skip',
                    help_text="Number of lines between `start_re` and actual "
                              "table. Only set if `start_re` is also set. "
                ),
                yc.ListElem(
                    'row_ignore', sub_elem=yc.StrElem(),
                    help_text="Rows to ignore."
                ),
                yc.ListElem(
                    'col_ignore', sub_elem=yc.StrElem(),
                    help_text="Columns to ignore."
                )
            ],
            defaults={
                'delimiter': ' ',
                'has_header': 'False',
                'by_column': 'False',
                'nth_start_re': '0'
            },
            validators={
                'has_header': ('True', 'False'),
                'by_column': ('True', 'False'),
                'col_num': int,
            }

        )

    def _check_args(self, **kwargs):

        col_names = kwargs['col_names']

        # try:
        #     if len(col_names) is not 0:
        #         if len(col_names) != kwargs['col_num']:
        #             raise pavilion.result.base.ResultError(
        #                 "Length of `col_names` does not match `col_num`."
        #             )
        # except ValueError:
        #     raise pavilion.result.base.ResultError(
        #         "`col_names` needs to be an integer."
        #     )
        try:
            int(kwargs['start_skip'])
            int(kwargs['row_num'])
            int(kwargs['col_num'])
        except ValueError:
            raise pavilion.result.base.ResultError(
                "num_skip, col_num, and row_num need to be integers"
            )

        return kwargs

    def __call__(self, test, file, delimiter=None, col_num=None,
                 has_header='', col_names=[], by_column=True,
                 start_re=None, row_num=None, start_skip=None,
                 nth_start_re=None, row_ignore=[], col_ignore=[]):

        lines = file.readlines()

        # Step 1: "Remove" unnecessary lines from file
        # (narrow down the list of lines Pavilion needs to look at)
        nth_start_re = int(nth_start_re)

        if start_re:
            lines_with_start_re = []
            start_re_regex = re.compile(start_re)
            for line_index in range(len(lines)):
                if start_re_regex.findall(lines[line_index]):
                    lines_with_start_re.append((line_index, lines[line_index]))

            if not lines_with_start_re:
                raise pavilion.result.base.ResultError(
                    "`start_re` not found in output."
                )

            start_num, start_line = lines_with_start_re[nth_start_re]
            try:
                end_num, end_line = lines_with_start_re[nth_start_re+1]
                lines = lines[start_num:end_num]
            except IndexError:
                lines = lines[start_num:]

        if start_skip:
            lines = lines[int(start_skip)+1:]

        if row_num:
            lines = lines[:int(row_num)]

        # Step 2: Redraw table
        # TODO: decide if I still want to ignore columns?
        if row_ignore:
            rows_to_remove = []
            for row_idx in row_ignore:
                rows_to_remove.append(lines[int(row_idx)])

            for rows in rows_to_remove:
                lines.remove(rows)

        if col_ignore:
            pass

        # Step 3: Use regex to get values
        # generate regular expression
        match_list = []
        value_regex = r'(\S+| )'
        corrected_delimiter = r'\s*?' + delimiter + r'\s*?'
        value_regex_list = []
        for i in range(int(col_num)):
            value_regex_list.append(value_regex)
        str_regex = corrected_delimiter.join(value_regex_list)
        str_regex = r'^\s*' + str_regex + r'\s*$'

        final_value_regex = re.compile(str_regex)
        for line in lines:
            match_list.extend(final_value_regex.findall(line))

        # if column names isn't specified, assume column names are the first
        # in the match_list
        # remove col names from match_list if it's there
        if not col_names:
            col_names = match_list.pop(0)
        else:
            if all(name in col_names for name in list(match_list[0])):
                match_list.pop(0)

        # sanitize column names in case there's duplicates
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

        # at this point, match_list should only contain the actual data
        result_dict = {}
        # row AND col -> dictionary of dictionaries
        if has_header in ['True', 'true']:
            if len(col_names) == int(col_num):
                col_names.pop(0)

            row_names = [] # assume first element in list is row name
            for m_idx in range(len(match_list)):
                row_names.append(match_list[m_idx][0])
                match_list[m_idx] = match_list[m_idx][1:]

            for col_idx in range(len(col_names)):
                result_dict[col_names[col_idx]] = {}
                for row_idx in range(len(row_names)):
                    result_dict[col_names[col_idx]][row_names[row_idx]] = \
                        match_list[row_idx][col_idx]

            # 'flip' the dictionary if by_column is set to False (default)
            if by_column == 'False':
                tmp_dict = {}
                for rname in row_names:
                    tmp_dict[rname] = {}
                    for cname in col_names:
                        tmp_dict[rname][cname] = result_dict[cname][rname]
                result_dict = tmp_dict

        # col only -> dictionary of lists
        else:
            for col_idx in range(len(col_names)):
                result_dict[col_names[col_idx]] = []
                for row_match in match_list:
                    result_dict[col_names[col_idx]].append(row_match[col_idx])

        return result_dict

