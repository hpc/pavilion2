"""This module contains a variety of helper functions that implement
common tasks, like command-line output and date formatting. These should
generally be used to help make Pavilion consistent across its code and
plugins.
"""

# This file contains assorted utility functions.

from pathlib import Path
import csv
import json
import os
import re
import subprocess
import sys
import textwrap
import shutil
import itertools
from collections import defaultdict, UserString

# Setup colors as part of the fprint function itself.
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
"""
Pavilion provides the standard 3/4 bit colors. They can be accessed through
this dictionary, or directly as attributes in the utils modules. ::

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


def flat_walk(path, *args, **kwargs):
    """Perform an os.walk on path, but return a flattened list of every file
    and directory found.

:param Path path: The path to walk with os.walk.
:param args: Any additional positional args for os.walk.
:param kwargs: Any additional kwargs for os.walk.
:returns: A list of all directories and files in or under the given path.
:rtype list[Path]:
    """

    paths = []

    for directory, dirnames, filenames in os.walk(str(path), *args, **kwargs):
        directory = Path(directory)
        for dirname in dirnames:
            paths.append(directory / dirname)

        for filename in filenames:
            paths.append(directory / filename)

    return paths


def get_mime_type(path):
    """Use the filemagic command to get the mime type of a file. Returned as a
    tuple of category and subtype.

    :param Path path: The path to the file to examine.
    :rtype: (str, str)
    :returns: category, subtype"""

    ftype = subprocess.check_output(['file',
                                     # Don't print the filename
                                     '-b',
                                     # Mime types are more sane to deal with
                                     '--mime-type',
                                     str(path)])

    # Get rid of whitespace and convert to unicode, and split
    parts = ftype.strip().decode().split('/', 2)

    category = parts[0]
    subtype = parts[1] if len(parts) > 1 else None

    return category, subtype


def symlink_copy(src, dst):
    """Makes an absolute symlink from src to dst.
    :param str src: The file to which the symlink will point.
    :param str dst: The symlink file to create.
    """

    src = os.path.realpath(src)

    return os.symlink(src, dst)


ID_DIGITS = 7
ID_FMT = '{id:0{digits}d}'


def make_id_path(base_path, id_):
    """Create the full path to an id directory given its base path and
    the id.
    :param Path base_path: The path to where id directories are stored.
    :param int id_: The id number
    :rtype: Path
    """

    return base_path / (ID_FMT.format(id=id_, digits=ID_DIGITS))


def get_login():
    """Get the current user's login, either through os.getlogin or
    the environment, or the id command."""

    try:
        return os.getlogin()
    except OSError:
        pass

    if 'USER' in os.environ:
        return os.environ['USER']

    try:
        name = subprocess.check_output(['id', '-un'],
                                       stderr=subprocess.DEVNULL)
        return name.decode('utf8').strip()
    except Exception:
        raise RuntimeError(
            "Could not get the name of the current user.")


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
           sep=' ', file=sys.stdout):
    """Print with automatic wrapping, bullets, and other features.

    :param args: Standard print function args
    :param int color: ANSI color code to print with.
    :param str bullet: Print the first line with this 'bullet' string,
        and the following lines indented to match..
    :param str sep: The standard print sep argument.
    :param file: Stream to print.
    :param int width: Wrap the text to this width.
    """

    args = [str(a) for a in args]
    if color is not None:
        print('\x1b[{}m'.format(color), end='', file=file)

    out_str = sep.join(args)
    for paragraph in str.splitlines(out_str):
        lines = textwrap.wrap(paragraph, width=width)
        lines = '\n'.join(lines)

        if bullet:
            lines = textwrap.indent(lines, bullet, lines.startswith)

        print(lines, file=file)

    if color is not None:
        print('\x1b[0m', end='', file=file)


class PavEncoder(json.JSONEncoder):
    """Adds Path encoding to our JSON encoder."""

    def default(self, o):  # pylint: disable=E0202
        if isinstance(o, Path):
            return super().default(str(o))
        else:
            return super().default(str(o))


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
"""

    CODE_RE = re.compile(r'^[0-9;]+$')
    ANSI_RE = re.compile(r'\x1b\[([0-9;]*)m')
    ANSI_FMT = '\x1b[{code}m{data}\x1b[0m'

    def __init__(self, data, code=None):
        """Parse the given data string into ANSI code colored blocks, and then
        wrap any components that aren't colored in the given code.
        :param str data: The string to color.
        :param str code: The code to color it with. Should be an ANSI argument
        set; integers separated by semicolons.
        """

        if code is not None:
            code = str(code)
            if not self.CODE_RE.match(code):
                raise ValueError("Invalid ANSI code: '{}'".format(code))

        parts = self._parse(data)
        formatted = []
        pcode = None

        for part, pcode in parts:
            if pcode is None:
                pcode = code

            if pcode is None:
                formatted.append(part)
            elif part:
                formatted.append(self.ANSI_FMT.format(code=pcode, data=part))

        self.data = ''

        super().__init__(''.join([str(s) for s in formatted]))
        self.carryover_code = pcode

    def _parse(self, data):
        """Break data into separate ansi coded chunks.
        :param str data:
        :returns A list of (str, code) tuples for each part of the string.
            Uncoded segments will have None as the code.
        :rtype: list((str,str))
        """

        matches = list(self.ANSI_RE.finditer(str(data)))

        start = 0
        parts = []
        code = None

        for match in matches:
            parts.append((data[start:match.start()], code))

            start = match.end()
            code = match.groups()[0]
            code_parts = code.split(';')
            # If a code ends in 0 or nothing, that's a reset.
            if code_parts[-1] in ('0', ''):
                code = None

        parts.append((data[start:], code))

        return parts

    def __len__(self):
        """Return the length without escapes."""
        return len(self.clean())

    def clean(self):
        """Remove all ANSI escapes from the string data."""

        return self.ANSI_RE.sub('', self.data)

    _WHITESPACE = ' \t\n\r\x0b\x0c'
    WORD_PUNCT = r'[\w!"\'&.,?]'
    WHITESPACE = r'[%s]' % re.escape(_WHITESPACE)
    NOWHITESPACE = '[^' + WHITESPACE[1:]
    WORDSEP_RE = re.compile(r'''
        ( # any whitespace
          {ws}+ |
          -
        )'''.format(ws=WHITESPACE), re.VERBOSE)
    del WORD_PUNCT, NOWHITESPACE

    def _chunks(self):
        """Break the text into chunks. Only non-empty chunks are returned.

        :rtype: list(ANSIString)
        """

        chunks = []
        carryover = None
        for chunk in self.WORDSEP_RE.split(self.data):
            if not chunk:
                continue

            if not chunk.strip():
                chunk = ' '
            chunk = ANSIString(chunk, code=carryover)
            carryover = chunk.carryover_code
            chunks.append(chunk)

        return chunks

    def wrap(self, width):
        """Wrap this string to the given width, much like the textwrap module
        does.

- Colorization wraps too.
- All whitespace is transformed into a single space.
- Words are broken on single hyphens or whitespace only.
- Long words are wrapped.

:param int width: The width to wrap to.
:raises ValueError: For invalid widths.
:returns: A list of wrapped ANSIStrings
"""

        if width <= 0:
            raise ValueError(
                "Width parameter must be a positive int. Got {}"
                .format(width))

        chunks = self._chunks()
        chunks.reverse()

        lines = []

        line = []
        line_len = 0
        while chunks:
            chunk = chunks.pop()

            # Skip whitespace that would start a line
            if chunk.clean() == ' ' and line_len == 0:
                continue

            c_len = len(ANSIString(chunk))

            # If the line is empty, put the next (non-whitespace) thing there.
            if line_len == 0:
                line.append(chunk[:width])
                # Our chunk may exceed the width. Save the rest for next time.
                remainder = ANSIString(chunk[width:], chunk.carryover_code)
                if remainder:
                    chunks.append(remainder)

                line_len += len(chunk[:width])

            # Add the next chunk if it's small enough.
            elif c_len + line_len <= width:
                line.append(chunk)
                line_len += c_len

            # No more space for the next line -- wrap.
            else:
                # We'll use this chunk next time.
                chunks.append(chunk)
                line = [str(l) for l in line]
                lines.append(ANSIString(''.join(line)))
                line = []
                line_len = 0

        return lines

    def __getitem__(self, item):
        parts = self._parse(self.data)
        parts.reverse()
        length = len(self)


        if isinstance(item, slice):
            start = item.start if item.start is not None else 0
            stop = item.stop if item.stop is not None else length
            step = item.step if item.step is not None else 1
        else:
            start = item
            stop = item + 1
            step = 1

        reverse = False
        if start < 0:
            start = length + start
        if stop < 0:
            stop = length + stop
        if step < 0:
            reverse = True
            start, stop = stop, start
            step = -step

        pos = 0
        # Tuples of (str_part, color)
        bits = []
        while pos < stop and parts:
            substr, color = parts.pop()
            if start > pos + len(substr):
                continue
            bits.append((substr[start-pos:stop-pos:step], color))
            pos += len(substr)

        # Reverse all of our output if our step was negative
        if reverse:
            for i in range(len(bits)):
                substr, bcode = bits[i]
                bits[i] = ''.join(list(reversed(substr))), bcode
        else:
            # We need to bits normally, so don't do it if
            # things should be backwards.
            bits.reverse()

        # Combine bits that are the same color.
        out_str = []
        last_code = None
        bit = None
        bcode = None
        while bits:
            bit_parts = []
            if bit is None:
                bit, bcode = bits.pop()
                bit_parts.append(bit)
                last_code = bcode

            while bits and bcode == last_code:
                bit_parts.append(bit)
                bit, bcode = bits.pop()
            if last_code is not None:
                out_str.append(self.ANSI_FMT.format(
                    data=''.join(bit_parts),
                    code=last_code))
            else:
                out_str.append(''.join(bit_parts))
            last_code = bcode

        return ANSIString(''.join(out_str))

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

        return padding_left + self.data + padding_right


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
        titles[field] = field_title

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
            try:
                data = info.get('format', '{0}').format(data)
            except ValueError:
                print("Bad format for data. Format: {0}, data: {1}"
                      .format(info.get('format', '{0}'),
                              repr(data)), file=sys.stderr)
                raise

            # Cast all data as ANSI strings, so we can get accurate lengths
            # and use ANSI friendly text wrapping.
            data = ANSIString(data)

            # Appends the length of all rows at a given field longer than the
            # title. Effectively forces that the minimum column width be no
            # less than the title.
            if len(data) > len(titles[field]):
                column_widths[field].append(len(data))

            formatted_row[field] = data
        formatted_rows.append(formatted_row)

    # Gets dictionary with largest width, and smallest width for each field.
    # Also updates the default column_Widths dictionary to hold the max values
    # for each column.
    min_widths = {field: min(widths) for field, widths in column_widths.items()}
    max_widths = {field: max(widths) for field, widths in column_widths.items()}
    column_widths = {field: max(widths) for field, widths in
                     column_widths.items()}

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
        for width in range(*boundaries[fld]):
            wrap_total = 0

            for row in formatted_rows:
                wrap_total += len(row[field].wrap(width=width))

            field_wraps_by_width[fld][width] = wrap_total

    # Calculates the max number of wraps for a given column width
    # combination.
    best_combo = None
    least_wraps = None

    # Checks all possible combinations.
    for combo in itertools.product(*(range(*bound) for bound in boundaries)):
        # Only populates list with combinations equal to current window
        # size if table width was the reason for wrapping
        if sum(combo) != window_width:
            continue

        wrap_count = 0
        for fld in range(len(fields)):  # pylint: disable=C0200
            wrap_count += field_wraps_by_width[fld][combo[fld]]

        # Updates minimum wraps with the smallest amount of wraps seen
        # so far.
        if least_wraps is None or wrap_count <= least_wraps:
            least_wraps = wrap_count
            best_combo = combo
            if wrap_count == 0:
                break

    # The base width of the table may be less the the terminal width.
    if best_combo is not None:
        for fld in range(len(fields)):
            column_widths[fields[fld]] = best_combo[fld]

    title_length = sum(column_widths.values())

    if pad:
        title_length = title_length + 2 * len(fields)

    title_format = ' {{0:{0}s}} '.format(title_length)
    # Generate the format string for each row.
    col_formats = []

    for field in fields:
        format_str = '{{{field_name}:{width}s}}' \
            .format(field_name=field, width=column_widths[field])
        if pad:
            format_str = ' ' + format_str + ' '
        col_formats.append(format_str)
    row_format = '|'.join(col_formats)

    # Add 2 dashes to each break line if we're padding the data
    brk_pad_extra = 2 if pad else 0
    horizontal_break = '+'.join(['-' * (column_widths[field] + brk_pad_extra)
                                 for field in fields])
    if border:
        row_format = '|' + row_format + '|'
        horizontal_break = '+' + horizontal_break + '+'
        title_format = '|' + title_format + '|'

    row_format += '\n'
    horizontal_break += '\n'
    title_format += '\n'

    wrap_rows = []
    # Reformats all the rows
    for row in formatted_rows:
        wraps = {}
        # Creates wrap list that holds list of strings for the wrapped text
        for field in fields:
            wraps[field] = row[field].wrap(width=column_widths[field])

        num_lines = 0
        # Gets the largest number of lines, so we know how many iterations
        # to do when printing
        for field in wraps.keys():
            number_of_wraps = len(wraps[field])
            if number_of_wraps > num_lines:
                num_lines = number_of_wraps

        # Populates current row with the first wrap
        for field in fields:
            try:
                row[field] = wraps[field][0]
            except IndexError as err:
                continue

        wrap_rows.append(row)
        # Creates a new row for each line of text required
        for line in range(1, num_lines):
            wrap_row = {}
            for field in fields:
                if line >= len(wraps[field]):
                    wrap_row[field] = ''
                else:
                    wrap_row[field] = wraps[field][line]

            wrap_rows.append(wrap_row)

    try:
        if border:
            outfile.write(horizontal_break)
        if title:
            outfile.write(title_format.format(title))
            outfile.write(horizontal_break)

        outfile.write(row_format.format(**titles))
        outfile.write(horizontal_break)
        for row in wrap_rows:
            outfile.write(row_format.format(**row))

        if border:
            outfile.write(horizontal_break)
        outfile.write('\n')

    except IOError:
        # We may get a broken pipe, especially when the output is piped to
        # something like head. It's ok, just move along.
        pass
