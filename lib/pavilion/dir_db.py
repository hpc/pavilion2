"""Manage 'id' directories. The name of the directory is an integer, which
essentially serves as a filesystem primary key."""

import os
import shutil
from datetime import datetime
from typing import Callable, List
from pathlib import Path

from pavilion import lockfile
from pavilion import test_run
from pavilion import output
from pavilion.status_file import STATES


ID_DIGITS = 7
ID_FMT = '{id:0{digits}d}'

PKEY_FN = 'next_id'

def make_id_path(base_path, id_):
    """Create the full path to an id directory given its base path and
    the id.

    :param Path base_path: The path to where id directories are stored.
    :param int id_: The id number
    :rtype: Path
    """

    return base_path / (ID_FMT.format(id=id_, digits=ID_DIGITS))


def reset_pkey(id_dir: Path) -> None:
    """Reset the the 'next_id' for the given directory by deleting
    the pkey file ('next_id') if present."""

    with lockfile.LockFile(id_dir/'.lockfile', timeout=1):
        try:
            (id_dir/PKEY_FN).unlink()
        except OSError:
            pass


def create_id_dir(id_dir: Path) -> (int, Path):
    """In the given directory, create the lowest numbered (positive integer)
    directory that doesn't already exist.

:param Path id_dir: Path to the directory that contains these 'id'
    directories
:returns: The id and path to the created directory.
:raises OSError: on directory creation failure.
:raises TimeoutError: If we couldn't get the lock in time.
"""

    lockfile_path = id_dir/'.lockfile'
    with lockfile.LockFile(lockfile_path, timeout=1):
        next_fn = id_dir/PKEY_FN

        next_valid = True

        if next_fn.exists():
            try:
                with next_fn.open() as next_file:
                    next_id = int(next_file.read())

                next_id_path = make_id_path(id_dir, next_id)

                if next_id_path.exists():
                    next_valid = False

            except (OSError, ValueError):
                # In either case, on failure, invalidate the next file.
                next_valid = False
        else:
            next_valid = False

        if not next_valid:
            # If the next file's id wasn't valid, then find the next available
            # id directory the hard way.

            ids = list(os.listdir(str(id_dir)))
            # Only return the test directories that could be integers.
            ids = [id_ for id_ in ids if id_.isdigit()]
            ids = [int(id_) for id_ in ids]
            ids.sort()

            # Find the first unused id.
            next_id = 1
            while next_id in ids:
                next_id += 1

            next_id_path = make_id_path(id_dir, next_id)

        next_id_path.mkdir()
        with next_fn.open('w') as next_file:
            next_file.write(str(next_id + 1))

        return next_id, next_id_path

def default_filter(_: Path) -> bool:
    """Pass every path."""

    return True

def is_hex(string: str) -> bool:
    """Determines if passed string is valide hex or not.
    :param string: A string to check.
    :return bool: True if hex, False, if not hex.
    """

    try:
        int(string, 16)
    except ValueError as err:
        return False

    return True

def select(id_dir: Path,
           filter_func: Callable[[Path], bool] = default_filter,
           build_dirs: bool = False) -> List[Path]:
    """Return a list of all test paths in the given id_dir that pass the
    given filter function. The paths returned are guaranteed (within limits)
    to be an id directory, and only paths that pass the filter function
    are returned."""

    passed = []
    for path in id_dir.iterdir():
        if not build_dirs:
            if path.name.isdigit() and path.is_dir():
                if filter_func(path):
                    passed.append(path)
        else:
            if is_hex(path.name) and path.is_dir():
                if filter_func(path):
                    passed.append(path)

    return passed

def delete(id_dir: Path,
           filter_func: Callable[[Path], bool] = default_filter,
           verbose: bool = False) -> int:
    """Deletes a directory and it's entire contents.

    :param id_dir: The directory to iterate through
    :param verbose: True or False based on if you want verbose output. Default
                    is false.
    :return int count: The number of directories removed.
    """

    count = 0

    lock_path = id_dir.with_suffix('.lock')
    with lockfile.LockFile(lock_path):
        for path in select(id_dir, filter_func):
            try:
                shutil.rmtree(path)
            except OSError as err:
                output.fprint("Could not remove {} {}: "
                              "{}".format(id_dir.name, path, err),
                              color=output.YELLOW)
                continue
            count += 1
            if verbose:
                output.fprint("Removed {} {}.".format(id_dir.name,
                                                      path.name))

    reset_pkey(id_dir)
    return count

