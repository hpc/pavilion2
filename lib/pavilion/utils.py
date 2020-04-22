"""This module contains a variety of helper functions that implement
common tasks, like command-line output and date formatting. These should
generally be used to help make Pavilion consistent across its code and
plugins.
"""

# This file contains assorted utility functions.

import os
import subprocess
import zipfile

from pathlib import Path

# Setup colors as part of the fprint function itself.


def dir_contains(file, directory):
    """Check if 'file' is or is contained by 'directory'."""
    file = Path(file).resolve()
    directory = Path(directory).resolve()
    while file.parent != file:
        if file == directory:
            return True
        file = file.parent
    return False


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


class ZipFileFixed(zipfile.ZipFile):
    """Overrides the default behavior in ZipFile to preserve execute
    permissions."""
    def _extract_member(self, member, targetpath, pwd):

        ret = super()._extract_member(member, targetpath, pwd)

        if not isinstance(member, zipfile.ZipInfo):
            member = self.getinfo(member)

        perms = member.external_attr >> 16

        file_path = os.path.join(targetpath, member.filename)
        if perms != 0:
            try:
                os.chmod(file_path, perms)
            except OSError:
                pass

        return ret
