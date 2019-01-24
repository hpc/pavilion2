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
                                     '-b',            # Don't print the filename
                                     '--mime-types',  # Mime types are more sane to deal w/
                                     path])

    # Get rid of whitespace and convert to unicode, and split
    parts = ftype.strip().decode().split('/', 2)

    category = parts[0]
    subtype = parts[1] if len(parts) > 1 else None

    return category, subtype


def fix_permissions(pav_cfg, path):
    # Recursively the fix permissions of the given path such that both the group and owner
    # have read
