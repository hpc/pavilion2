"""
This module provides helper functions for printing and general output.

Pavilion provides the standard 3/4 bit colors. They can be accessed through
this dictionary, or directly as attributes in the utils modules.

..code:: python
utils.COLORS['RED']
utils.RED

**Available Colors:**

- BLACK
- RED
- GREEN
- YELLOW
- BLUE
- MAGENTA
- CYAN
- WHITE
- GREY
- GRAY
- BOLD
- FAINT
- UNDERLINE
"""

import csv
import datetime
import json
import pprint
import re
import shutil
import sys
import textwrap
import random
from collections import UserString, UserDict
from pathlib import Path
from typing import List, Dict

BLACK = 30
RED = 31
GREEN = 32
YELLOW = 33
BLUE = 34
MAGENTA = 35
CYAN = 36
WHITE = 37
GREY = 37
GRAY = 37
BOLD = 1
FAINT = 2
UNDERLINE = 4

#: Available colors.
COLORS = {
    'BLACK': BLACK,
    'RED': RED,
    'GREEN': GREEN,
    'YELLOW': YELLOW,
    'BLUE': BLUE,
    'MAGENTA': MAGENTA,
    'CYAN': CYAN,
    'WHITE': WHITE,
    'GREY': WHITE,
    'GRAY': WHITE,
    'BOLD': BOLD,
    'FAINT': FAINT,
    'UNDERLINE': UNDERLINE,
}


def get_relative_timestamp(base_time):
    """Print formatted time string based on the delta of time objects.
    :param float base_time: The datetime object to compare and format
    from.
    :returns: A formatted time string.
    :rtype str:
    """

    if not isinstance(base_time, float):
        return ''

    now = datetime.datetime.now()
    format_ = ['%Y', '%b', '%a', '%H:%M:%S']  # year, month, day, time

    base_time = datetime.datetime.fromtimestamp(base_time)

    for i in range(0, len(format_)):
        if now.strftime(format_[i]) != base_time.strftime(format_[i]):
            return base_time.strftime(" ".join(format_[i:]))

    return base_time.strftime(str(format_[3]))


def dbg_print(*args, color=YELLOW, file=sys.stderr, end="",
              pformat=True, **kwargs):
    """A colored print statement for debug printing. Use when you want to
print dbg statements and easily excise it later.

:param file: The file object to write to.
:param end: Default the ending to no newline (we do a pre-newline because
    of how unittest prints stuff.
:param int color: ANSI color code to print the string under.
:param bool pformat: Automatically apply pprint.pformat to args that are
    dicts or lists.
:param kwargs: Also accepts all ``print()`` kwargs.
"""
    start_escape = '\n\x1b[{}m'.format(color)

    if pformat:
        args = list(args)
        for i in range(len(args)):
            arg = args[i]
            if isinstance(arg, (dict, list)):
                args[i] = pprint.pformat(arg)

    print(start_escape, end='', file=file)
    print(*args, file=file, end='', **kwargs)
    print('\x1b[0m', end=end, file=file)
    sys.stderr.flush()


def clear_line(outfile):
    """Clear the last line written to output. Assumes the line ended with
    a \\r rather than a newline."""

    size = shutil.get_terminal_size().columns
    size = 80 if size == 0 else size

    outfile.write('\r')
    outfile.write(' '*size)
    outfile.write('\r')


def fprint(*args, color=None, bullet='', width=0, wrap_indent=0,
           sep=' ', file=sys.stdout, end='\n', flush=False, clear=False):
    """Print with automatic wrapping, bullets, and other features. Also accepts
    all print() kwargs.

    :param args: Standard print function args
    :param int color: ANSI color code to print with.
    :param str bullet: Print the first line with this 'bullet' string, and the
        following lines indented to match.
    :param str sep: The standard print sep argument.
    :param file: Stream to print.
    :param int wrap_indent: Indent lines (after the first) this number of
        spaces for each paragraph.
    :param Union[int,None] width: Wrap the text to this width. If 0, find the
        terminal's width and wrap to that.
    :param str end: String appended after the last value (default \\n)
    :param bool flush: Whether to forcibly flush the stream.
    :param bool clear: Perform a 'clear_line' before printing.
"""

    if clear:
        clear_line(file)

    args = [str(a) for a in args]
    if color is not None:
        print('\x1b[{}m'.format(color), end='', file=file)

    if width == 0:
        width = shutil.get_terminal_size().columns
        width = 80 if width == 0 else width

    wrap_indent = ' '*wrap_indent

    if width is not None:
        paragraphs = []
        out_str = sep.join(args)
        for paragraph in str.splitlines(out_str):
            lines = textwrap.wrap(paragraph, width=width,
                                  subsequent_indent=wrap_indent)
            lines = '\n'.join(lines)

            if bullet:
                lines = textwrap.indent(lines, bullet, lines.startswith)

            paragraphs.append(lines)
        print('\n'.join(paragraphs), file=file, end='')
    else:
        out_str = sep.join(args)
        print(out_str, file=file, end='')

    if color is not None:
        print('\x1b[0m', file=file, end='')

    print(end, end='', file=file, flush=flush)


def json_dumps(obj, skipkeys=False, ensure_ascii=True,
               check_circular=True, allow_nan=True, indent=None,
               separators=None, default=None, sort_keys=False, **kw):
    """Dump data to string as per the json dumps function, but using
our custom encoder."""

    return json.dumps(obj, cls=PavEncoder,
                      skipkeys=skipkeys,
                      ensure_ascii=ensure_ascii,
                      check_circular=check_circular,
                      allow_nan=allow_nan,
                      indent=indent,
                      separators=separators,
                      default=default,
                      sort_keys=sort_keys,
                      **kw)


def json_dump(obj, file, skipkeys=False, ensure_ascii=True,
              check_circular=True, allow_nan=True, indent=None,
              separators=None, default=None, sort_keys=False, **kw):
    """Dump data to string as per the json dumps function, but using
our custom encoder."""

    return json.dump(obj, file, cls=PavEncoder,
                     skipkeys=skipkeys,
                     ensure_ascii=ensure_ascii,
                     check_circular=check_circular,
                     allow_nan=allow_nan,
                     indent=indent,
                     separators=separators,
                     default=default,
                     sort_keys=sort_keys,
                     **kw)


def output_csv(outfile, fields, rows, field_info=None, header=False):
    """Write the given rows out as a CSV.

    :param outfile: The file object to write to.
    :param field_info: A dict of information on each field. See 'draw_table'
        below. Only the title field is used.
    :param fields: A list of fields to write, and in what order.
    :param rows: A list of dictionaries to write, in the given order.
    :param header: Whether to generate a header row.
    :return: None
    """

    row_data = []

    if field_info is None:
        field_info = {}

    # Generate a header row, using the title from field_info for each row if
    # given.
    if header:
        header_row = [field_info.get(field, {}).get('title', field)
                      for field in fields]
        row_data = [header_row]

    for row in rows:
        row_list = [row.get(f, '') for f in fields]
        row_data.append(row_list)

    try:
        writer = csv.writer(outfile)
        writer.writerows(row_data)
    except IOError:
        # Handle broken pipes. It's ok when this happens.
        pass


class ANSIString(UserString):
    """Create a string with an implicit ANSI display mode. The ansi code will be
used when the string is formatted.

    hello = ANSIStr("Hello World", utils.RED)
    print(hello)

    :ivar data: The raw string data.
"""

    ANSI_START = '\x1b[{code}m'
    ANSI_END = '\x1b[0m'

    def __init__(self, data, code=None):
        """Parse the given data string into ANSI code colored blocks, and then
        wrap any components that aren't colored in the given code.
        :param Union[str,ANSIString,None] data: The string to color.
        :param str code: The code to color it with. Should be an ANSI argument
        set; integers separated by semicolons.
        """

        if isinstance(data, ANSIString):
            self.code = code if code is not None else data.code
            data = data.data
        else:
            self.code = code

        super().__init__(data)

    FORMAT_RE = re.compile(
        r'''
        (?:(?P<fill>.)?(?P<align>[<>^]))?  # The fill and alignment
        (?P<min_width>\d+)?                # Minimum field width
        (?P<type>s)?$                      # Field type conversion
        ''',
        flags=re.VERBOSE)

    FORMAT_DEFAULTS = {
        'fill': ' ',
        'align': '<',
        'min_width': 0,
        'type': 's',
    }

    def wrap(self, width=70):
        """Wrap the text as with textwrap, but return ANSIString objects
        with the same ANSI code applied."""

        lines = []
        for paragraph in str.splitlines(self.data):
            lines.extend([
                ANSIString(row, code=self.code)
                for row in textwrap.wrap(paragraph, width=width)])

        return lines

    def colorize(self):
        """Return the string wrapped in the appropriate ANSI escapes."""

        if self.code is None:
            return self.data

        data = [
            self.ANSI_START.format(code=self.code),
            self.data,
            self.ANSI_END
        ]

        return ''.join(data)

    def __format__(self, format_spec):

        match = self.FORMAT_RE.match(format_spec)

        if match is None:
            raise ValueError(
                "Invalid format for ANSIString: '{}'"
                .format(format_spec)
            )

        fmt = match.groupdict()
        for key in self.FORMAT_DEFAULTS.keys():
            if fmt[key] is None:
                fmt[key] = self.FORMAT_DEFAULTS[key]

        min_width = int(fmt['min_width'])

        length = len(self)

        padding_left = ''
        padding_right = ''

        if fmt['align'] == '<':
            padding_right = (min_width - length) * fmt['fill']
        elif fmt['align'] == '>':
            padding_left = (min_width - length) * fmt['fill']
        elif fmt['align'] == '^':
            diff = min_width - length
            padding_left = (diff//2) * fmt['fill']
            padding_right = (diff//2 + diff % 2) * fmt['fill']

        parts = []

        parts.extend((padding_left, self.colorize(), padding_right))

        return ''.join(parts)


# It's ok to wrap words longer than this
MAX_WORD_LEN = 15
DEFAULT_BORDER_CHARS = {
    'vsep': '|',
    'hsep': '-',
    'isep': '+',
}


def draw_table(outfile, fields, rows,
               field_info=None, border=False, pad=True,
               border_chars=None, header=True, title=None, table_width=None):
    """Prints a table from the given data, dynamically setting
the column width.

:param outfile: The file-like object to write to.
:param list fields: A list of the fields to include, in the given order. These
    also serve as the default column titles (Capitalized).
:param list(dict) rows: A list of data dictionaries. A None may be included to
    denote that a horizontal line row should be inserted.
:param dict field_info: Should be a dictionary of field names (all of
    which are optional) where the value is a dict of:

  - title - The column header for this field. Defaults to the
    field name, capitalized.
  - transform - a function that takes the field value,
    transforms it in some way, and returns the result to be inserted
    into the table.
  - format - a format string in the new style format syntax.
    It will expect the data for that row as arg 0. IE: '{0:2.2f}%'.
  - default - A default value for the field. A blank is
    printed by default.
  - no_wrap - a boolean that determines if a field will be
    wrapped or not.
  - max_width - the max width for a given field.
  - min_width - the min width for a given field.
:param bool border: Put a border around the table. Defaults False.
:param bool header: Print a header row of column names followed by a
    horizontal seperator. Defaults to True.
:param bool pad: Put a space on either side of each header and row entry.
    Default True.
:param dict border_chars: A dictionary of characters for drawing the table
    borders and separators. Expects the keys 'vsep', 'hsep', 'isep'. By default
    these are '|', '-', and '+'.
:param str title: Add the given title above the table. Default None
:param int table_width: By default size table to the terminal width. If set
    size the table to this width instead.
:return: None

**Examples**

A simple table: ::

    from pavilion import utils

    # The table data is expected as a list of dictionaries with identical keys.
    # Not all dictionary fields will necessarily be used. Commands will
    # typically generate the rows dynamically...
    rows = [
        {'color': 'BLACK',  'code': 30, 'usage': 'Default'},
        {'color': 'RED',    'code': 31, 'usage': 'Fatal Errors'},
        {'color': 'GREEN',  'code': 32, 'usage': 'Warnings'},
        {'color': 'YELLOW', 'code': 33, 'usage': 'Discouraged'},
        {'color': 'BLUE',   'code': 34, 'usage': 'Info'}
    ]
    # The data columns to print (and their default column labels).
    columns = ['color', 'usage']

    utils.draw_table(
        outfile=sys.stdout,
        field_info={},

    # Produces a table like this:
    #
    #  Color  | Usage
    # --------+--------------
    #  BLACK  | Default
    #  RED    | Fatal Errors
    #  GREEN  | Warnings
    #  YELLOW | Discouraged
    #  BLUE   | Info

A more complicated example: ::

    from pavilion import utils
    import sys

    rows = [
        {'color': 'BLACK',   'code': 30, 'usage': 'Default'},
        {'color': 'RED',     'code': 31, 'usage': 'Fatal Errors'},
        {'color': 'GREEN',   'code': 32, 'usage': 'Warnings'},
        {'color': 'YELLOW',  'code': 33, 'usage': 'Discouraged'},
        {'color': 'BLUE',    'code': 34, 'usage': 'Info'},
        {'color': 'CYAN',    'code': 35},
        {'color': 'MAGENTA', 'code': 36},

    ]

    columns = ['color', 'code', 'usage']
    field_info = {
        # Colorize the color column with a transform function.
        'color': {
            'transform': lambda t: utils.ANSIString(t, utils.COLORS.get(t)),
        },
        # Format and add a better column header to the 'code' column.
        'code': {
            'title': 'ANSI Code',
            'format': '0x{0:x}',
        },
        # Put in a default for our missing usage values.
        # (The default is just to leave the column empty.)
        'usage': {
            'default': 'Whatever you want.'
        }
    }

    utils.draw_table(
        outfile=sys.stdout,
        field_info=field_info,
        fields=columns,
        rows=rows,
        # Add a border. Why not?
        border=True,
        # No padding between the data and column seperators.
        pad=False,
        title="A Demo Table."
    )

    # Produces a table like this (plus with the color names in color):
    #
    # +-------+---------+------------------+
    # | A Demo Table.                      |
    # +-------+---------+------------------+
    # |Color  |ANSI Code|Usage             |
    # +-------+---------+------------------+
    # |BLACK  |0x1e     |Default           |
    # |RED    |0x1f     |Fatal Errors      |
    # |GREEN  |0x20     |Warnings          |
    # |YELLOW |0x21     |Discouraged       |
    # |BLUE   |0x22     |Info              |
    # |CYAN   |0x23     |Whatever you want.|
    # |MAGENTA|0x24     |Whatever you want.|
    # +-------+---------+------------------+
"""

    if field_info is None:
        field_info = {}

    border_chars = {} if border_chars is None else border_chars
    vsep = border_chars.get('vsep', DEFAULT_BORDER_CHARS['vsep'])
    hsep = border_chars.get('hsep', DEFAULT_BORDER_CHARS['hsep'])
    isep = border_chars.get('isep', DEFAULT_BORDER_CHARS['isep'])
    if len(vsep) != 1 or len(hsep) != 1 or len(isep) != 1:
        raise RuntimeError("Separators must each be one character long.")

    # Column widths populates with a range of values, the minimum being the
    # length of the given field title, and the max being the longest entry in
    # that column
    titles = dt_field_titles(fields, field_info)

    # Format the rows according to the field_info format specifications.
    rows = dt_format_rows(rows, fields, field_info)
    if header:
        rows.insert(0, titles)

    # Calculate the min and max widths for each column.
    min_widths, max_widths = dt_calculate_widths(rows, fields, field_info)

    # Calculate the overall table width.
    table_width = dt_calc_table_width(min_widths, pad, border, table_width)

    # Adjust the column widths to minimize wraps
    column_widths = dt_auto_widths(rows, table_width, min_widths, max_widths)

    # Calculate the title format
    title_length = sum(column_widths.values())
    if pad:
        title_length = title_length + 2 * len(fields)
    title_format = ' {{0:{0}s}} '.format(title_length)
    if border:
        if pad:
            title_format = vsep + ' ' + title_format + ' ' + vsep
        else:
            title_format = vsep + title_format + vsep
    title_format += '\n'

    # Generate the table break line.
    # Add 2 dashes to each break line if we're padding the data
    brk_pad_extra = 2 if pad else 0
    horizontal_break = isep.join([hsep * (column_widths[field] + brk_pad_extra)
                                  for field in fields])
    if border:
        horizontal_break = isep + horizontal_break + isep
    horizontal_break += '\n'

    # Output the table.
    try:
        if border:
            outfile.write(horizontal_break)
        if title:
            outfile.write(title_format.format(title))
            outfile.write(horizontal_break)

        for row_i, row in enumerate(rows):

            # Collect a list of dicts where the index is the subrow,
            # the key is the field and the value is the text.
            wrap_rows = [{}]
            for field in fields:
                wraps = row[field].wrap(width=column_widths[field])
                for i, wrap in enumerate(wraps):
                    if i >= len(wrap_rows):
                        wrap_rows.append({})
                    wrap_rows[i].update({field: wrap})

            for wrap_row in wrap_rows:
                outfile.write(dt_format_row(
                    wrap_row, fields, column_widths, pad, border, vsep))

            # Write the horizontal break after the header, if we have one.
            if row_i == 0 and header:
                outfile.write(horizontal_break)

        if border:
            outfile.write(horizontal_break)

    except IOError:
        # We may get a broken pipe, especially when the output is piped to
        # something like head. It's ok, just move along.
        pass


def dt_field_titles(fields: List[str], field_info: dict) \
        -> Dict[str, ANSIString]:
    """Get the titles for each column in the table."""

    titles = {}
    for field in fields:
        default_title = field.replace('_', ' ').capitalize()
        field_title = field_info.get(field, {}).get('title', default_title)
        # Gets the length of column title, adds it to the list of column widths
        titles[field] = ANSIString(field_title)

    return titles


def dt_format_rows(rows, fields, field_info):
    """Format each field value in each row according to the format
    specifications. Also converts each field value into an ANSIStr so we
    can rely on it's built in '.wrap' method."""

    blank_row = {field: ANSIString('') for field in fields}

    formatted_rows = []
    for row in rows:
        formatted_row = {}
        if row is None:
            # 'None' rows just produce an empty row.
            formatted_rows.append(blank_row)
            continue

        for field in fields:
            # Get the data, or it's default if provided.
            info = field_info.get(field, {})
            data = row.get(field, info.get('default', ''))
            # Transform the data, if a transform is given
            if data != '' and data is not None:
                try:
                    data = info.get('transform', lambda a: a)(data)
                except (ValueError, AttributeError, KeyError):
                    data = '<transform error on {}>'.format(data)

            if isinstance(data, ANSIString):
                ansi_code = data.code
                data = str(data)
            else:
                ansi_code = None

            # Format the data
            col_format = info.get('format', '{0}')
            try:
                formatted_data = col_format.format(data)
            except ValueError:
                print("Bad format for data. Format: {0}, data: {1}"
                      .format(col_format, repr(data)), file=sys.stderr)
                raise

            # Cast all data as ANSI strings, so we can get accurate lengths
            # and use ANSI friendly text wrapping.
            data = ANSIString(formatted_data, code=ansi_code)

            formatted_row[field] = data
        formatted_rows.append(formatted_row)

    return formatted_rows


def dt_calculate_widths(rows, fields, field_info):
    """Calculate the min and max width for each column, based on the length
    of all values in that column and the size of the words in each value."""

    # Gets dictionary with largest width, and smallest width for each field.
    # Also updates the default column_Widths dictionary to hold the max values
    # for each column.
    min_widths = {}
    max_widths = {}

    for field in fields:
        all_words = sum([row[field].split() for row in rows], [])
        max_widths[field] = max([len(row[field]) for row in rows])
        longest_word = ''
        for word in all_words:
            if len(word) > len(longest_word):
                longest_word = word

        min_widths[field] = min(MAX_WORD_LEN, len(longest_word))

    for field in fields:
        # If user specified ignoring wrapping on a given field, it will set the
        # minimum width equal to the largest entry in that field.
        if 'no_wrap' in field_info.get(field, {}).keys():
            min_widths[field] = max_widths[field]
        # If user defined a max width for a given field it overrides the
        # maximum width here.
        if 'max_width' in field_info.get(field, {}).keys():
            max_widths[field] = field_info[field]['max_width']
        # If user defined a min width for a given field it overrides the
        # minimum width here.
        if 'min_width' in field_info.get(field, {}).keys():
            min_widths[field] = field_info[field]['min_width']
        # Ensures that the max width for a given field is always larger or
        # at least equal to the minimum field width.
        if max_widths[field] < min_widths[field]:
            max_widths[field] = min_widths[field]

    return min_widths, max_widths


def dt_calc_table_width(min_widths: Dict[str, int], pad: bool, border: bool,
                        table_width: int) -> int:
    """Calculate the width of the table based on all of the table parameters
    and column min widths.

    :param min_widths: Minimum column width by column.
    :param pad: Whether to pad each column with a space on either side
        of the divider.
    :param border: Whether the tables has a border.
    :param table_width: The user specified table width.
    """

    fields = list(min_widths.keys())

    # Add divider widths
    divider_size = 3 if pad else 1
    deco_size = divider_size * (len(fields) - 1)
    # Add the side spacing
    deco_size += 2 if pad else 0
    # Add border widths
    if border:
        border_size = 2 if pad else 1
        deco_size += border_size * 2

    # Gets the effective window width.
    if table_width is None:
        table_width = shutil.get_terminal_size().columns
        table_width = 80 if table_width == 0 else table_width
    table_width -= deco_size

    # Makes sure window is at least large enough to display our smallest
    # possible table
    total_min = sum(min_widths.values())
    if total_min > table_width:
        table_width = total_min

    return table_width


def dt_auto_widths(rows, table_width, min_widths, max_widths):
    """Calculate an 'optimal' width for each column.
    If the maximum width of the column is less than the table width, use that.
    Otherwise follow the algorithm which finds the column that will benefit
    the most from a single character of width increase. In case of a tie,
    two characters of width are considered, and so on. Remaining extra
    spaces are distributed amongst the final tied columns. To limit time cost
    make a best guess using 20 random rows.
    """

    mxwidth = sum(max_widths.values())
    if mxwidth <= table_width:
        return max_widths

    fields = set(min_widths.keys())

    mnwidth = sum(min_widths.values())
    extra_spaces = table_width - mnwidth

    final_widths = min_widths.copy()

    maxrows = 20
    nrows   = min(len(rows), maxrows)
    rowsamp = [rows[0]] + random.sample(rows[1:], nrows)

    # Limit to just the first 20 rows for speed.
    # rows = rows[:100]
    rowbyfield = {field: [row[field].data for row in rowsamp] for field in fields}
    # row2 = {field: " ".join(rows) for field, rows in rowbyfield.items()}

    def calc_wraps(fld_, width_):
        """Calculate the wraps for a given field at the given width."""
        wtot = 0
        for row in rowbyfield[fld_]:
            wtot += len(textwrap.wrap(row, width=width_))
        return wtot

    incr = 1
    # Consume the additional spaces available by growing the columns according
    # to which column would benefit the most from the extra space. If there
    # is a tie, increase the number of spaces considered.
    growable_fields = list(fields)
    while extra_spaces and growable_fields:
        best_fields = []
        best_diff = 0

        # Find the 'best_fields' to add 'incr' byte to.
        for field in growable_fields.copy():
            curr_width = final_widths[field]
            incr_width = curr_width + incr

            max_width = max_widths[field]

            if curr_width == max_width:
                growable_fields.remove(field)
                continue

            if incr_width > max_width:
                # Don't consider this column for an increase if the increase
                # exceeds the max width for the column.
                continue

            curr_wraps = calc_wraps(field, curr_width)

            # Make sure we don't exceed the max width for the column.
            incr_wraps = calc_wraps(field, incr_width)

            diff = (curr_wraps - incr_wraps)

            if diff == 0:
                if incr_width == max_width:
                    # Increasing the width of this column won't help. Skip it from
                    # now on.
                    growable_fields.remove(field)
                continue

            # If this field beats all previous, make it the best.
            if diff > best_diff:
                best_diff = diff
                best_fields = [field]
            # If we tie, add it to the list of the best.
            elif diff == best_diff:
                best_fields.append(field)

        if len(best_fields) == 1:
            # Add incr bytes to the winner
            extra_spaces -= incr
            final_widths[best_fields[0]] += incr
            incr = 1
        elif incr == extra_spaces:
            # If we've run out of bytes to consider, distribute them evenly
            # amongst the tied winners.
            extra_spaces -= incr
            for field in best_fields:
                final_widths[field] += incr // len(best_fields)
        else:
            # Otherwise, increase the increment and try again.
            incr += 1

    return final_widths

ast = ANSIString('')
def dt_format_row(row, fields, widths, pad, border, vsep):
    """Format a single row according to the table parameters and widths."""
    out = []
    if border:
        out.append(vsep)
    if pad:
        out.append(' ')

    if pad:
        col_sep = ' ' + vsep + ' '
    else:
        col_sep = vsep

    for field_i, field in enumerate(fields):
        if field_i != 0:
            out.append(col_sep)
        data = row.get(field, ast)
        if isinstance(data, ANSIString):
            color_data = data.colorize()
            out.append(color_data)
        else:
            out.append(data)
        out.append(' '*(widths[field] - len(data)))

    if pad:
        out.append(' ')
    if border:
        out.append(vsep)
    out.append('\n')

    return ''.join(out)


class PavEncoder(json.JSONEncoder):
    """Adds various pavilion types to our JSON encoder, so it can
    automatically encode them."""

    def default(self, o):  # pylint: disable=E0202
        """Handle additional types."""

        if isinstance(o, Path):
            return o.as_posix()
        # Just auto-convert anything that looks like a dict.
        elif isinstance(o, (dict, UserDict)):
            return dict(o)

        return super().default(o)
