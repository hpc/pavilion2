"""Manage 'id' directories. The name of the directory is an integer, which
essentially serves as a filesystem primary key."""

import json
import os
from typing import Callable, List
from pathlib import Path

from pavilion import lockfile
from pavilion import utils

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

#  select once so we only make one filter.
def filter_all(_: Path) -> bool:

    path = _
    try:
        if args.complete:
            complete_path = path / 'RUN_COMPLETE'
            if not complete_path.exists():
                return False
        if args.incomplete:
            incomplete_path = path / 'RUN_COMPLETE'
            if incomplete_path.exists():
                return False
        if args.user:
            if str(path.owner()) != args.user[0]:
                return False
        if args.sys_name:
            with open(path / 'variables') as var_file:
                vars = json.load(var_file)
                if vars['sys']['sys_name'] != args.sys_name:
                    return False
        if args.passed:
            path = _ / 'results.json'
            with open(path) as file:
                result = json.load(file)
                if result['result'] != 'PASS':
                    return False
        if args.failed:
            path = _ / 'results.json'
            with open(path) as file:
                result = json.load(file)
                if result['result'] != 'FAIL':
                    return False
        if args.older_than:
            path = _ / 'variables'
            cutoff = retrieve_datetime(args.older_than)
            with open(path) as file:
                result = json.load(file)
                if float(result['pav']['timestamp'][0]) > cutoff:
                    return False
        if args.newer_than:
            path = _ / 'variables'
            cutoff = retrieve_datetime(args.newer_than)
            with open(path) as file:
                result = json.load(file)
                if float(result['pav']['timestamp'][0]) < cutoff:
                    return False
    except (FileNotFoundError, NotADirectoryError):
        return False
    return True


def default_order(_: Path) -> list:
    """Ignore order and return whole list"""
    list = []
    for path in id_dir.iterdir():
        if path.name.isdigit() and path.is_dir():
            list.append(path)
    return path


def order_list(_: Path) -> int:
    path = _
    with open(path / 'variables') as var_file:
        vars = json.load(var_file)
        time = vars['pav']['timestamp']
    return time


def select(id_dir: Path,
           filter_func: Callable[[Path], bool] = default_filter,
           order_func: Callable[[Path], int] = default_order,
           args=None, ) -> List[Path]:
    """Return a list of all test paths in the given id_dir that pass the
    given filter function. The paths returned are guaranteed (within limits)
    to be an id directory, and only paths that pass the filter function
    are returned."""
    from pavilion.output import dbg_print

    list = []
    for path in id_dir.iterdir():
        if path.name.isdigit() and path.is_dir:

            time = order_func(path)
            dbg_print(time)
            list.append((time, path))

    if not args.older:
        list.sort(reverse=True)
    else:
        list.sort()

    passed = []
    for path in list:
        if filter_func(path[1]):
            passed.append(path[1])
        if args.limit == len(passed):
            return passed
    return passed
