"""This module contains a variety of helper functions that implement
common tasks, like command-line output and date formatting. These should
generally be used to help make Pavilion consistent across its code and
plugins.
"""

import errno
import os
import subprocess
import zipfile
from pathlib import Path
from typing import Iterator


# Python 3.5 issue. Python 3.6 Path.resolve() handles this correctly.
# pylint: disable=protected-access
def resolve_path(path, strict=False):
    """Stolen straight from python3.6 pathlib."""

    sep = '/'
    accessor = path._accessor
    seen = {}

    def _resolve(path_, rest):
        if rest.startswith(sep):
            path_ = ''

        for name in rest.split(sep):
            if not name or name == '.':
                # current dir
                continue
            if name == '..':
                # parent dir
                path_, _, _ = path_.rpartition(sep)
                continue
            newpath = path_ + sep + name
            if newpath in seen:
                # Already seen this path
                path_ = seen[newpath]
                if path_ is not None:
                    # use cached value
                    continue
                # The symlink is not resolved, so we must have a symlink loop.
                raise RuntimeError("Symlink loop from %r" % newpath)
            # Resolve the symbolic link
            try:
                target = accessor.readlink(newpath)
            except OSError as err:
                if err.errno != errno.EINVAL and strict:
                    raise
                # Not a symlink, or non-strict mode. We just leave the path
                # untouched.
                path_ = newpath
            else:
                seen[newpath] = None  # not resolved symlink
                path_ = _resolve(path_, target)
                seen[newpath] = path_  # resolved symlink

        return path_

    # NOTE: according to POSIX, getcwd() cannot contain path components
    # which are symlinks.
    base = '' if path.is_absolute() else os.getcwd()
    return _resolve(base, str(path)) or sep


def dir_contains(file, directory):
    """Check if 'file' is or is contained by 'directory'."""

    file = Path(file)
    directory = Path(directory)
    while file.parent != file:
        if file == directory:
            return True
        file = file.parent
    return False


def flat_walk(path, *args, **kwargs) -> Iterator[Path]:
    """Perform an os.walk on path, but simply generate each item walked over.

:param Path path: The path to walk with os.walk.
:param args: Any additional positional args for os.walk.
:param kwargs: Any additional kwargs for os.walk.
"""

    for directory, dirnames, filenames in os.walk(str(path), *args, **kwargs):
        directory = Path(directory)
        for dirname in dirnames:
            yield directory / dirname

        for filename in filenames:
            yield directory / filename


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


def relative_to(other: Path, base: Path) -> Path:
    """Get a relative path from base to other, even if other isn't contained
    in base."""

    if not base.is_dir():
        raise ValueError(
            "The base '{}' must be a directory."
            .format(base))

    base = Path(resolve_path(base))
    other = Path(resolve_path(other))

    bparts = base.parts
    oparts = other.parts

    i = 0
    for i in range(min([len(bparts), len(oparts)])):
        if bparts[i] != oparts[i]:
            if i <= 1:
                # The paths have nothing in common, just return the other path.
                return other
            else:
                o_steps = i
                up_dirs = len(bparts) - i
                break
    else:
        o_steps = i + 1
        up_dirs = 0

    ref = ('..',) * up_dirs + oparts[o_steps:]
    return Path(*ref)


def repair_symlinks(base: Path) -> None:
    """Makes all symlinks under the path 'base' relative."""

    base = base.resolve()

    for file in flat_walk(base):

        if file.is_symlink():
            # Found a second thing that pathlib doesn't do (though a requst
            # for Path.readlink has already been merged in the Python develop
            # branch)
            target = Path(os.readlink(file.as_posix()))
            target = Path(resolve_path(target))
            sym_dir = file.parent
            if target.is_absolute() and dir_contains(target, base):
                rel_target = relative_to(target, sym_dir)
                file.unlink()
                file.symlink_to(rel_target)
