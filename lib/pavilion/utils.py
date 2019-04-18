# This file contains assorted utility functions.

import csv
import json
import os
import re
import sys
import subprocess
from pavilion import lockfile


def flat_walk(path, *args, **kwargs):
    """Perform an os.walk on path, but return a flattened list of every file
    and directory found.
    :param str path: The path to walk with os.walk.
    :param args: Any additional positional args for os.walk.
    :param kwargs: Any additional kwargs for os.walk.
    :returns: A list of all directories and files in or under the given path.
    :rtype list:
    """

    paths = []

    for directory, dirnames, filenames in os.walk(path, *args, **kwargs):
        for dirname in dirnames:
            paths.append(os.path.join(directory, dirname))

        for filename in filenames:
            paths.append(os.path.join(directory, filename))

    return paths


def get_mime_type(path):
    """Use a filemagic command to get the mime type of a file. Returned as a
    tuple of category and subtype.
    :param str path: The path to the file to examine.
    :returns: category, subtype"""

    ftype = subprocess.check_output(['file',
                                     # Don't print the filename
                                     '-b',
                                     # Mime types are more sane to deal with
                                     '--mime-type',
                                     path])

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
    the id."""
    return os.path.join(base_path, ID_FMT.format(id=id_, digits=ID_DIGITS))


def create_id_dir(id_dir):
    """In the given directory, create the lowest numbered (positive integer)
    directory that doesn't already exist.
    :param str id_dir: Path to the directory that contains these 'id'
        directories
    :returns: The id and path to the created directory.
    :raises OSError: on directory creation failure.
    :raises TimeoutError: If we couldn't get the lock in time.

    """

    lockfile_path = os.path.join(id_dir, '.lockfile')
    with lockfile.LockFile(lockfile_path, timeout=1):
        ids = os.listdir(id_dir)
        # Only return the test directories that could be integers.
        ids = filter(str.isdigit, ids)
        ids = filter(lambda d: os.path.isdir(os.path.join(id_dir, d)), ids)
        ids = list(map(int, ids))
        ids.sort()

        # Find the first unused id.
        id_ = 1
        while id_ in ids:
            id_ += 1

        path = make_id_path(id_dir, id_)
        os.mkdir(path)

    return id_, path


def cprint(*args, color=33, **kwargs):
    """Print with pretty colors, so it's easy to find."""
    start_escape = '\x1b[{}m'.format(color)

    args = [start_escape] + list(args) + ['\x1b[0m']

    return print(*args, **kwargs)


def output_json(outfile, context):
    """Just dump the context out as raw JSON.
    :param outfile: The file object to write to.
    :param context: A serializable object containing nothing but serializable
    objects.
    :return:
    """
    try:
        json.dump(context, outfile)
    except IOError:
        # Handle a broken pipe
        pass


def output_csv(outfile, field_info, fields, rows):
    """Write the given rows out as a CSV
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


class ANSIStr:
    MODES = {
        'black':        30,
        'red':          31,
        'green':        32,
        'yellow':       33,
        'blue':         34,
        'magenta':      35,
        'cyan':         36,
        'white':        37,
        'bold':         1,
        'underscore':   4,
        'concealed':    8,
        'bg_black':     40,
        'bg_red':       41,
        'bg_green':     42,
        'bg_yellow':    43,
        'bg_blue':      44,
        'bg_magenta':   45,
        'bg_cyan':      46,
        'bg_white':     47,
    } 

    def __init__(self, string, modes=None):
        """Create a string with an implicit ANSI mode. When formatted, the
        string will be prepended with the ANSI escape for the given modes.
        It will otherwise behave like a normal string."""
    
        if modes is None:
            modes = []
        elif not isinstance(modes, (list, tuple)):
            modes = [modes]

        self.modes = []
        for mode in modes:
            if mode not in self.MODES:
                raise ValueError("Unknown ANSI graphics mode: {0}".format(mode))
            self.modes.append(str(self.MODES[mode]))

        self.string = string

    def __format__(self, format_spec):
        
        if self.modes:
            ansi_start = '\x1b[' + ';'.join(self.modes) + 'm'
        else:
            ansi_start = ''
        ansi_end = '\x1b[0m'
        formatted = format(self.string, format_spec)

        return ansi_start + formatted + ansi_end

    def __getattr__(self, attr):
        if attr not in self.__dict__:
            return getattr(self.string, attr)


ANSI_ESCAPE_RE = re.compile('\x1b\\[\\d+(;\\d+)*m')


def _plen(string):
    """Get the printable length of the given string."""

    # Remove ansi escape codes (only handles graphics mode changes)
    unescaped = ANSI_ESCAPE_RE.sub('', string)

    return len(unescaped)
 

def draw_table(outfile, field_info, fields, rows, border=False, pad=True,
               title=None):
    """Prints a table from the given data, setting column width as needed.
    :param outfile: The output file to write to. 
    :param field_info: Should be a dictionary of field names where the value
        is a dict of:
        ( title (optional) - The column header for this field. Defaults to the
            field name, capitalized.
          transform (optional) - a function that takes the field value,
            transforms it in some way, and returns the result to be inserted
            into the table.
          format (optional) - a format string in the new style format syntax.
            It will expect the data for that row as arg 0. IE: '{0:2.2f}%'.
          default (optional) - A default value for the field. A blank is
          printed by default.
    :param fields: A list of the fields to include, in the given order.
    :param rows: A list of data dictionaries. A None may be included to denote
        that a horizontal line row should be inserted.
    :param border: Put a border around the table. Defaults False.
    :param pad: Put a space on either side of each header and row entry.
        Default True.
    :param title: Add the given title above the table. Default None
    :return: None
    """

    column_widths = {}
    titles = {}
    for field in fields:
        default_title = field.replace('_', ' ').capitalize()
        field_title = field_info.get(field, {}).get('title', default_title)
        column_widths[field] = [len(field_title)]
        titles[field] = field_title

    blank_row = {}
    for field in fields:
        blank_row[field] = ''

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

            column_widths[field].append(_plen(data))
            formatted_row[field] = data
        formatted_rows.append(formatted_row)

    for field in column_widths.keys():
        column_widths[field] = max(column_widths[field])

    # We have to manually pad everything due to unicode and ansi escapes.
    for field, width in column_widths.items():
        for row in formatted_rows:
            data = row[field]
            dlen = _plen(data)
            row[field] = data + ' '*max(0, width - dlen) 

    # Find the total width of the table. 
    total_width = (sum(column_widths.values())  # column widths
                   + len(fields) - 1)           # | dividers
    if pad:
        total_width += len(fields)*2            # padding
    # Widen the last column if the title is longer than everything else.
    # The +2 is for title padding.
    title_len = len(title)
    if title is not None and (title_len + 2 > total_width):
        diff = title_len + 2 - total_width
        column_widths[fields[-1]] += diff

    title_format = ' {{0:{0}s}} '.format(total_width - 2)

    # Generate the format string for each row.
    col_formats = []
    for field in fields:
        format_str = '{{{field_name}:{width}}}'\
                     .format(field_name=field, width=column_widths[field])
        if pad:
            format_str = ' ' + format_str + ' '
        col_formats.append(format_str)
    row_format = '|'.join(col_formats)

    # Add 2 dashes to each break line if we're padding the data
    brk_pad_extra = 2 if pad else 0
    horizontal_break = '+'.join(['-'*(column_widths[field]+brk_pad_extra)
                                 for field in fields])
    if border:
        row_format = '|' + row_format + '|'
        horizontal_break = '+' + horizontal_break + '+'
        title_format = '|' + title_format + '|'

    row_format += '\n'
    horizontal_break += '\n'
    title_format += '\n'

    try:
        if border:
            outfile.write(horizontal_break)
        if title:
            outfile.write(title_format.format(title))
            outfile.write(horizontal_break)

        outfile.write(row_format.format(**titles))
        outfile.write(horizontal_break)
        for row in formatted_rows:
            outfile.write(row_format.format(**row))

        if border:
            outfile.write(horizontal_break)

        outfile.write('\n')
    except IOError:
        # We may get a broken pipe, especially when the output is piped to
        # something like head. It's ok, just move along.
        pass
