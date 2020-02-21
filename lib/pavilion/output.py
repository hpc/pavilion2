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
import itertools
import json
import re
import shutil
import sys
import textwrap
from collections import UserString, defaultdict, UserDict
from pathlib import Path

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


def get_relative_timestamp(base_dt):
    """Print formatted time string based on the delta of time objects.
    :param datetime base_dt: The datetime object to compare and format from.
    :returns: A formatted time string.
    :rtype str:
    """
    now = datetime.datetime.now()
    format_ = ['%Y', '%b', '%a', '%H:%M:%S']  # year, month, day, time

    for i in range(0, len(format_)):
        if now.strftime(format_[i]) != base_dt.strftime(format_[i]):
            return base_dt.strftime(" ".join(format_[i:]))

    return base_dt.strftime(str(format_[3]))


def dbg_print(*args, color=YELLOW, file=sys.stderr, end="", **kwargs):
    """A colored print statement for debug printing. Use when you want to
print dbg statements and easily excise it later.

:param file: The file object to write to.
:param end: Default the ending to no newline (we do a pre-newline because
    of how unittest prints stuff.
:param int color: ANSI color code to print the string under.
"""
    start_escape = '\n\x1b[{}m'.format(color)

    print(start_escape, end='', file=file)
    print(*args, file=file, end='', **kwargs)
    print('\x1b[0m', end=end, file=file)
    sys.stderr.flush()


def fprint(*args, color=None, bullet='', width=100,
           sep=' ', file=sys.stdout, end='\n', flush=False):
    """Print with automatic wrapping, bullets, and other features. Also accepts
    all print() kwargs.

    :param args: Standard print function args
    :param int color: ANSI color code to print with.
    :param str bullet: Print the first line with this 'bullet' string, and the
        following lines indented to match.
    :param str sep: The standard print sep argument.
    :param file: Stream to print.
    :param int width: Wrap the text to this width.
    :param str end: String appended after the last value (default \\n)
    :param bool flush: Whether to forcibly flush the stream.
"""

    args = [str(a) for a in args]
    if color is not None:
        print('\x1b[{}m'.format(color), end='', file=file)

    out_str = sep.join(args)
    if width is not None:
        for paragraph in str.splitlines(out_str):
            lines = textwrap.wrap(paragraph, width=width)
            lines = '\n'.join(lines)

            if bullet:
                lines = textwrap.indent(lines, bullet, lines.startswith)

            print(lines, file=file)
    else:
        print(out_str, file=file)

    if color is not None:
        print('\x1b[0m', end=end, file=file, flush=flush)


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


def output_csv(outfile, field_info, fields, rows):
    """Write the given rows out as a CSV.

    :param outfile: The file object to write to.
    :param field_info: A dict of information on each field. See 'draw_table'
        below. Only the title field is used.
    :param fields: A list of fields to write, and in what order.
    :param rows: A list of dictionaries to write, in the given order.
    :return: None
    """

    # Generate a header row, using the title from field_info for each row if
    # given.
    header_row = [field_info.get(field, {}).get('title', field)
                  for field in fields]
    row_data = [header_row]
    for row in rows:
        row_list = [row[f] for f in fields]
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
        :param Union[str,ANSIString] data: The string to color.
        :param str code: The code to color it with. Should be an ANSI argument
        set; integers separated by semicolons.
        """

        if isinstance(data, ANSIString):
            data = data.data
            self.code = code if code is not None else data.code
        else:
            self.code = code
            self.data = None

        super().__init__(data)

    FORMAT_RE = re.compile(
        r'''
        (?:(?P<fill>.)?(?P<align>[<>^]))?  # The fill and alignment
        (?P<min_width>\d+)?                # Minimum field width
        (?P<type>s)?$                     # Field type conversion
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

        return [ANSIString(row, code=self.code)
                for row in textwrap.wrap(self.data, width=width)]

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

        parts.extend((padding_left, self.data, padding_right))

        return ''.join(parts)


def format_row(row, fields, widths, pad, border):
    out = []
    if border:
        out.append('|')
    if pad:
        out.append(' ')

    for field_i in range(len(fields)):
        field = fields[field_i]
        if field_i != 0:
            if pad:
                out.append(' | ')
            else:
                out.append('|')
        data = row[field]
        if isinstance(data, ANSIString):
            color_data = data.colorize()
            out.append(color_data)
        else:
            out.append(data)
        out.append(' '*(widths[field] - len(data)))

    if pad:
        out.append(' ')
    if border:
        out.append('|')
    out.append('\n')

    return ''.join(out)


# It's ok to wrap words longer than this
MAX_WORD_LEN = 15


def draw_table(outfile, field_info, fields, rows, border=False, pad=True,
               title=None):
    """Prints a table from the given data, dynamically setting
the column width.

:param outfile: The file-like object to write to.
:param dict field_info: Should be a dictionary of field names where the value
  is a dict of:

  - title (optional) - The column header for this field. Defaults to the
    field name, capitalized.
  - transform (optional) - a function that takes the field value,
    transforms it in some way, and returns the result to be inserted
    into the table.
  - format (optional) - a format string in the new style format syntax.
    It will expect the data for that row as arg 0. IE: '{0:2.2f}%'.
  - default (optional) - A default value for the field. A blank is
    printed by default.
  - no_wrap (optional) - a boolean that determines if a field will be
    wrapped or not.
  - max_width (optional) - the max width for a given field.
  - min_width (optional) - the min width for a given field.
:param list fields: A list of the fields to include, in the given order. These
    also serve as the default column titles (Capitalized).
:param list(dict) rows: A list of data dictionaries. A None may be included to
    denote that a horizontal line row should be inserted.
:param bool border: Put a border around the table. Defaults False.
:param bool pad: Put a space on either side of each header and row entry.
    Default True.
:param str title: Add the given title above the table. Default None
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

    # Column widths populates with a range of values, the minimum being the
    # length of the given field title, and the max being the longest entry in
    # that column
    column_widths = {}
    titles = {}

    for field in fields:
        default_title = field.replace('_', ' ').capitalize()
        field_title = field_info.get(field, {}).get('title', default_title)
        # Gets the length of column title, adds it to the list of column widths
        column_widths[field] = [len(field_title)]
        titles[field] = ANSIString(field_title)

    blank_row = {}
    for field in fields:
        blank_row[field] = ANSIString('')

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
            data = info.get('transform', lambda a: a)(data)
            # Format the data
            col_format = info.get('format', '{0}')
            try:
                formatted_data = col_format.format(data)
            except ValueError:
                print("Bad format for data. Format: {0}, data: {1}"
                      .format(col_format, repr(data)), file=sys.stderr)
                raise

            if isinstance(data, ANSIString):
                ansi_code = data.code
            else:
                ansi_code = None

            # Cast all data as ANSI strings, so we can get accurate lengths
            # and use ANSI friendly text wrapping.
            data = ANSIString(formatted_data, code=ansi_code)

            # Appends the length of all rows at a given field longer than the
            # title. Effectively forces that the minimum column width be no
            # less than the title.
            if len(data) > len(titles[field]):
                column_widths[field].append(len(data))

            formatted_row[field] = data
        formatted_rows.append(formatted_row)

    rows = formatted_rows
    rows.insert(0, titles)

    # Gets dictionary with largest width, and smallest width for each field.
    # Also updates the default column_Widths dictionary to hold the max values
    # for each column.
    max_widths = {field: max(widths) for field, widths in column_widths.items()}
    min_widths = {}

    for field in fields:
        all_words = sum([row[field].split() for row in rows], [])
        longest_word = ''
        for word in all_words:
            if len(word) > len(longest_word):
                longest_word = word

        min_widths[field] = min(MAX_WORD_LEN, len(longest_word))

    for field in field_info:
        # If user specified ignoring wrapping on a given field, it will set the
        # minimum width equal to the largest entry in that field.
        if 'no_wrap' in field_info[field].keys():
            min_widths[field] = max_widths[field]
        # If user defined a max width for a given field it overrides the
        # maximum width here.
        if 'max_width' in field_info[field].keys():
            max_widths[field] = field_info[field]['max_width']
        # If user defined a min width for a given field it overrides the
        # minimum width here.
        if 'min_width' in field_info[field].keys():
            min_widths[field] = field_info[field]['min_width']
        # Ensures that the max width for a given field is always larger or
        # at least equal to the minimum field width.
        if max_widths[field] < min_widths[field]:
            max_widths[field] = min_widths[field]

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
    window_width = shutil.get_terminal_size().columns
    window_width -= deco_size

    # Makes sure window is at least large enough to display are smallest
    # possible table
    total_min = sum(min_widths.values())
    if total_min > window_width:
        window_width = total_min

    boundaries = []
    for field in fields:

        # Get updated max width for a column provided every other column is
        # at its minimum width.
        max_width = window_width - sum(min_widths.values()) + min_widths[field]

        # Only updated if the max_Width is less than current max value.
        if max_width < max_widths[field]:
            max_widths[field] = max_width

        boundaries.append([min_widths[field], max_widths[field] + 1])

    # Pre-calculate the total wraps for each field at each possible
    # column width.
    field_wraps_by_width = defaultdict(dict)
    for fld in range(len(fields)):  # pylint: disable=C0200
        field = fields[fld]
        for width in range(boundaries[fld][0], boundaries[fld][1] + 1):
            wrap_total = 0

            for row in formatted_rows:

                wrap_total += len(row[field].wrap(width=width))

            field_wraps_by_width[fld][width] = wrap_total

    extra_spaces = window_width - sum(min_widths.values())
    final_widths = min_widths.copy()

    incr = 1
    while extra_spaces:
        best_fields = []
        best_diff = 0

        for fld in range(len(fields)):
            field = fields[fld]
            curr_width = final_widths[field]

            curr_wraps = field_wraps_by_width[fld].get(curr_width, 1)
            incr_wraps = field_wraps_by_width[fld].get(curr_width + incr, 1)
            diff = (curr_wraps-incr_wraps)

            if diff > best_diff:
                best_diff = diff
                best_fields = [field]
            elif diff == best_diff:
                best_fields.append(field)

        if len(best_fields) == 1 or incr == extra_spaces:
            extra_spaces -= incr
            incr = 1
            final_widths[best_fields[0]] += incr
        else:
            incr += 1

    title_length = sum(final_widths.values())

    if pad:
        title_length = title_length + 2 * len(fields)

    title_format = ' {{0:{0}s}} '.format(title_length)

    # Add 2 dashes to each break line if we're padding the data
    brk_pad_extra = 2 if pad else 0
    horizontal_break = '+'.join(['-' * (final_widths[field] + brk_pad_extra)
                                 for field in fields])
    if border:
        horizontal_break = '+' + horizontal_break + '+'
        title_format = '|' + title_format + '|'

    horizontal_break += '\n'
    title_format += '\n'

    try:
        if border:
            outfile.write(horizontal_break)
        if title:
            outfile.write(title_format.format(title))
            outfile.write(horizontal_break)

        for row_i in range(len(rows)):
            row = rows[row_i]

            wrap_rows = defaultdict(lambda: defaultdict(lambda: ''))
            # Creates wrap list that holds list of strings for the wrapped text
            for field in fields:
                wraps = row[field].wrap(width=final_widths[field])
                for wrap_i in range(len(wraps)):
                    wrap_row = wrap_rows[wrap_i]
                    wrap_row[field] = wraps[wrap_i]

            # Turn the wrapped rows into a list sorted by index
            wrap_rows = [wrap_rows[i] for i in sorted(list(wrap_rows.keys()))]

            for wrap_row in wrap_rows:
                outfile.write(format_row(wrap_row, fields, final_widths, pad,
                                         border))

            if row_i == 0:
                outfile.write(horizontal_break)

    except IOError:
        # We may get a broken pipe, especially when the output is piped to
        # something like head. It's ok, just move along.
        pass


class PavEncoder(json.JSONEncoder):
    """Adds various pavilion types to our JSON encoder, so it can
    automatically encode them."""

    def default(self, o):  # pylint: disable=E0202
        if isinstance(o, Path):
            return str(o)
        elif isinstance(o, datetime.datetime):
            return o.isoformat()
        # Just auto-convert anything that looks like a dict.
        elif isinstance(o, (dict, UserDict)):
            return dict(o)

        return super().default(o)
