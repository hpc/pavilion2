"""Manage 'id' directories. The name of the directory is an integer, which
essentially serves as a filesystem primary key."""

import os
import shutil
from datetime import datetime
from typing import Callable, List
from pathlib import Path
from typing import Callable, List, Iterable, Any

from pavilion import lockfile
from pavilion import test_run
from pavilion import output
from pavilion.status_file import STATES


ID_DIGITS = 7
ID_FMT = '{id:0{digits}d}'

PKEY_FN = 'next_id'

def make_id_path(base_path, id_) -> Path:
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

def select(id_dir: Path,
           filter_func: Callable[[Any], bool] = default_filter,
           transform: Callable[[Path], Any] = lambda v: v,
           order_func: Callable[[Any], Any] = None,
           order_asc: bool = True,
           fn_base: int = 10,
           limit: int = None) -> List[Any]:
    """
    :param id_dir: The dir_db directory to select from.
    :param filter_func:
    :param transform:
    :param order_func:
    :param order_asc:
    :param limit:
    :returns: A filtered, ordered list of transformed objects.

    Other arguments are as per select_from.
    """

    return select_from(
        paths=id_dir.iterdir(),
        transform=transform,
        filter_func=filter_func,
        order_func=order_func,
        order_asc=order_asc,
        fn_base=fn_base,
        limit=limit,
    )


def select_from(paths: Iterable[Path],
                filter_func: Callable[[Any], bool] = default_filter,
                transform: Callable[[Path], Any] = lambda v: v,
                order_func: Callable[[Any], Any] = None,
                order_asc: bool = True,
                fn_base: int = 10,
                limit: int = None) -> List[Any]:
    """Return a list of test paths in the given id_dir, filtered, ordered, and
    potentially limited.
    :param paths: A list of paths to filter, order, and limit.
    :param transform: Function to apply to each path before applying filters
        or ordering. The filter and order functions should expect the type
        returned by this.
    :param filter_func: A function that takes a directory, and returns whether
        to include that directory. True -> include, False -> exclude
    :param order_func: A function that returns a comparable value for sorting,
        as per the list.sort keys argument. Items for which this returns
        None are removed.
    :param order_asc: Whether to sort in ascending or descending order.
    :param fn_base: Number base for file names. 10 by default, ensure dir name
        is a valid integer.
    :param limit: The max items to return. None denotes return all.
    :returns: A filtered, ordered list of transformed objects.
    """

    items = []
    for path in paths:
        if not path.is_dir():
            continue
        try:
            int(path.name, fn_base)
        except ValueError:
            continue

        try:
            item = transform(path)
        except ValueError:
            continue

        if not filter_func(item):
            continue

        if order_func is not None and order_func(item) is None:
            continue

        items.append(item)

    if order_func is not None:
        items.sort(key=order_func, reverse=not order_asc)

    return items[:limit]


def paths_to_ids(paths: List[Path]) -> List[int]:
    """Convert a list of list of dir_db paths to ids.

    :param paths: A list of id paths.
    :raises ValueError: For invalid paths
    """

    ids = []
    for path in paths:
        try:
            ids.append(int(path.name))
        except ValueError:
            raise ValueError(
                "Invalid dir_db path '{}'".format(path.as_posix()))
    return ids

def delete(id_dir: Path, filter_func: Callable[[Path],bool]=default_filter,
           verbose: bool=False):
    """Delete all id directories in a given path that match the given filter.
    :param id_dir: The directory to iterate through.
    :param filter_func: A passed filter function, to be passed to select.
    :param verbose: Verbose output.
    :return int count: The number of directories removed.
    :return list msgs: Any messages generated during removal.
    """

    count = 0
    msgs = []

    lock_path = id_dir.with_suffix('.lock')
    with lockfile.LockFile(lock_path):
        if id_dir.name is 'test_runs':
            for item in select(id_dir=id_dir, filter_func=filter_func,
                               transform=test_run.TestAttributes):
                try:
                    shutil.rmtree(item.path)
                except (OSError, TypeError) as err:
                    msgs.append("Could not remove {} {}: {}"
                                .format(id_dir.name, item.path, err))
                    continue
                count += 1
                if verbose:
                    msgs.append("Removed {} {}.".format(id_dir.name,
                                                        str(item.id)
                                                        .zfill(7)))
        else:
            for item in select(id_dir=id_dir, filter_func=filter_func):
                try:
                    shutil.rmtree(item)
                except (OSError,TypeError) as err:
                    msgs.append("Could not remove {} {}: {}"
                                .format(id_dir.name, item, err))
                    continue
                count += 1
                if verbose:
                    msgs.append("Removed {} {}.".format(id_dir.name,
                                                        item.name))
    reset_pkey(id_dir)
    return count, msgs
