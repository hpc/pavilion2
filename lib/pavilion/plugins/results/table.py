import re

import yaml_config as yc
from pavilion.result import parsers, ResultError


class Table(parsers.ResultParser):
    """Parses tables."""

    def __init__(self):
        super().__init__(
            name='table',
            description="Parses tables.",
            config_elems=[
                yc.StrElem(
                    'line_num', required=False,
                    help_text="Optional. Number of lines after `start_re` "
                              "that Pavilion should look at. "
                ),
                yc.StrElem(
                    'row_ignore_re',
                    help_text="Optional. Regex of lines to ignore when "
                              "parsing the table. Mainly for skipping lines "
                              "of dashes and similar."
                ),
                yc.StrElem(
                    'table_end_re',
                    help_text="The regular expression that denotes the end "
                              "of the table. Defaults to a '^\\s*$' "
                              "(a line of nothing but whitespace)."
                ),
                yc.StrElem(
                    'delimiter',
                    help_text="Delimiter that splits the data in each row. "
                              "Defaults to whitespace two or more whitespace "
                              "characters ('\\s\\s+'). Regardless of "
                              "the delimiter, whitespace is always stripped "
                              "from each either end of extracted data."
                ),
                yc.ListElem(
                    'col_names', required=False, sub_elem=yc.StrElem(),
                    help_text="The column names. By default, the first line "
                              "of the table is considered to be the column "
                              "names. Data for columns with an empty name"
                              "(ie '') are not included in the results."
                ),
                yc.StrElem(
                    'col_num', required=True,
                    help_text="Number of columns in table, including row "
                              "names, if there is such a column."
                ),
                yc.StrElem(
                    'has_row_labels',
                    help_text="Set True if there is a column for row names. "
                              "Row data "

                ),
                yc.StrElem(
                    'by_column',
                    help_text="Set to True if the user wants to organize the "
                              "nested dictionaries by columns. Default False. "
                              "Only set if `has_header` is True. "
                              "Otherwise, Pavilion will ignore."
                ),
                yc.ListElem(
                    'col_ignore', sub_elem=yc.StrElem(),
                    help_text="(Coming soon) Columns to ignore."
                )
            ],
            defaults={
                'delimiter':    ' ',
                'has_header':   'False',
                'by_column':    'False',
            },
            validators={
                'has_header': ('True', 'False'),
                'by_column':  ('True', 'False'),
                'col_num':    int,
            }

        )

    def _check_args(self, **kwargs):

        col_names = kwargs['col_names']

        try:
            if len(col_names) != 0:
                if len(col_names) != kwargs['col_num']:
                    raise ResultError(
                        "Length of `col_names` does not match `col_num`."
                    )
        except ValueError:
            raise ResultError(
                "`col_names` needs to be an integer."
            )

        return kwargs

    def __call__(self, file, delimiter_re=None, col_num=None,
                 has_header='', col_names=None, by_column=True,
                 line_num=None, table_end_re=None,
                 row_ignore_re=None, col_ignore=None):

        col_names = [] if col_names is None else col_names
        row_ignore_re = re.compile(row_ignore_re)
        table_end_re = re.compile(table_end_re)
        delimiter_re = re.compile(delimiter_re)

        lines = []
        # Record the first non-empty line we find as a point of reference
        # for errors.
        reference_line = None

        # Collect all the lines that belong to our table.
        for line in file:
            if reference_line is None and line.strip():
                reference_line = line

            # Skip lines that match this regex.
            if row_ignore_re.search(line) is not None:
                continue

            # Stop collecting lines after this.
            if table_end_re.search(line) is not None:
                break

            lines.append(line)

        if reference_line is None:
            reference_line = file.readline()

        if not lines:
            raise ResultError(
                'Found table at "{}", but all lines were ignored by the '
                'row_ignore_re \'{}\'.'
                .format(reference_line, row_ignore_re.pattern))

        lines.reverse()

        if not col_names:
            col_names = delimiter_re.split(lines.pop())

        row_idx = 0

        while lines:
            row = delimiter_re.split(lines.pop())



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

            row_names = []  # assume first element in list is row name
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
