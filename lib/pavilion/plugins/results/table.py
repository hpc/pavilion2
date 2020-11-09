"""Parse values from tables."""

import re

import yaml_config as yc
from pavilion.result import parsers, ResultError


class Table(parsers.ResultParser):
    """Parses tables."""

    def __init__(self):
        super().__init__(
            name='table',
            description="Parses tables of data, creating a mapping of "
                        "row to a mapping of data by column.",
            config_elems=[
                yc.StrElem(
                    'delimiter_re',
                    help_text="Delimiter that splits the data in each row. "
                              "Defaults to whitespace one or more "
                              "characters ('\\s+'). Regardless of "
                              "the delimiter, whitespace is always stripped "
                              "from each either end of extracted data. "
                              "Whitespace delimited tables with missing "
                              "values are not supported."
                ),
                yc.StrElem(
                    'row_ignore_re',
                    help_text="Optional. Regex of lines to ignore when "
                              "parsing the table. Mainly for skipping "
                              "divider lines and similar. Make sure your "
                              "regex matches the whole line with '^' and "
                              "'$'. Defaults to ignore rows composed only of "
                              "'|', '-', or '+' (plus whitespace)."
                ),
                yc.StrElem(
                    'table_end_re',
                    help_text="The regular expression that denotes the end "
                              "of the table. Defaults to a '^\\s*$' "
                              "(a line of nothing but whitespace)."
                ),
                yc.ListElem(
                    'col_names', required=False, sub_elem=yc.StrElem(),
                    help_text="Optional. The column names. By default, "
                              "the first line of the table is considered to be "
                              "the column names. Data for columns with an "
                              "empty name (ie '') are not included in the "
                              "results."
                ),
                yc.StrElem(
                    'has_row_labels',
                    help_text="Optional. The first column will be used as the "
                              "row label. If this is False or the first column "
                              "is empty, the row will labeled 'row_n' starting "
                              "from 1. Row labels will be normalized and "
                              "altered for uniqueness."
                ),
                yc.StrElem(
                    'by_column',
                    help_text="Set to True if the user wants to organize the "
                              "nested dictionaries by columns. Default False. "
                              "Only set if `has_header` is True. "
                              "Otherwise, Pavilion will ignore."
                ),
            ],
            defaults={
                'delimiter_re':     r'\s+',
                'row_ignore_re':    r'^(\s*(\||\+|-|=)+)+\s*$',
                'table_end_re':     r'^\s*$',
                'col_names':       [],
                'has_row_labels':   'True',
                'by_column':        'False',
            },
            validators={
                'has_header': ('True', 'False'),
                'by_column':  ('True', 'False'),
                'delimiter_re': re.compile,
                'table_end_re': re.compile,
            }

        )

    NON_WORD_RE = re.compile(r'\W')

    def __call__(self, file, delimiter_re=None,
                 col_names=None, by_column=True,
                 table_end_re=None, has_row_labels=False,
                 row_ignore_re=None):

        col_names = [] if col_names is None else col_names
        row_ignore_re = re.compile(row_ignore_re)
        table_end_re = re.compile(table_end_re)
        delimiter_re = re.compile(delimiter_re)
        by_column = by_column == "True"
        has_row_labels = has_row_labels == "True"

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
                'row_ignore_re \'{}\' or ended prematurely by a bad '
                'table_end_re \'{}\'.'
                .format(reference_line, row_ignore_re.pattern,
                        table_end_re.pattern))

        lines.reverse()

        if not col_names:
            col_names = [col.strip() for col in delimiter_re.split(lines.pop())]

            if has_row_labels:
                col_names = col_names[1:]

        # Replace non-alpha num characters with '_', and make non-unique
        # columns with unique names.
        fixed_col_names = []
        for col in col_names:
            col = col.lower()
            col = ncol = self.NON_WORD_RE.sub('_', col)
            i = 2

            while ncol and ncol in fixed_col_names:
                ncol = '{}_{}'.format(col, i)

            if ncol and ncol[0] in '0134576789':
                ncol = 'c_' + ncol

            fixed_col_names.append(ncol)
        col_names = fixed_col_names

        row_idx = 0
        table = {}

        while lines:
            row = delimiter_re.split(lines.pop())
            row.reverse()

            if has_row_labels:
                row_label = row.pop().strip().lower()
                row_label = self.NON_WORD_RE.sub('_', row_label)
                # Devise a row label if one isn't given.
                if not row_label:
                    row_label = 'row_{}'.format(row_idx)

                # Row labels can't start with a number.
                if row_label[0] in '0123456789':
                    row_label = 'row_{}'.format(row_label)

                if row_label and row_label in table:
                    row_label = '{}_{}'.format(row_label, row_idx)
            else:
                row_label = 'row_{}'.format(row_idx)
            row_idx += 1

            row_data = {}

            for col in col_names:
                data = row.pop().strip() if row else None
                data = data if data else None
                if col:
                    row_data[col] = data

            table[row_label] = row_data

        if by_column:
            col_table = {}
            for row_name, row in table.items():
                for col_name, col_val in row.items():
                    col = col_table.get(col_name, {})
                    col[row_name] = col_val
                    col_table[col_name] = col

            return col_table
        else:
            return table
