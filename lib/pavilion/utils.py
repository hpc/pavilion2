# This file contains assorted utility functions.

import os
import subprocess


def flat_walk(path, *args, **kwargs):
    """Perform an os.walk on path, but return a flattened list of every file and directory found.
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
    """Use a filemagic command to get the mime type of a file. Returned as a tuple of
    category and subtype.
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


def cprint(*args, color=33, **kwargs):
    """Print with pretty colors, so it's easy to find."""
    start_escape = '\x1b[{}m'.format(color)

    args = [start_escape] + list(args) + ['\x1b[0m']

    return print(*args, **kwargs)


def fix_permissions(pav_cfg, path):
    # Recursively the fix permissions of the given path such that both the group and owner
    # have read
    pass