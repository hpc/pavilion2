"""Manage 'id' directories. The name of the directory is an integer, which
essentially serves as a filesystem primary key."""

import json
import os
import shutil
import time
import logging
from pathlib import Path
from typing import Callable, List, Iterable, Any, Dict, NewType
from collections import namedtuple

from pavilion import lockfile
from pavilion import permissions

ID_DIGITS = 7
ID_FMT = '{id:0{digits}d}'

PKEY_FN = 'next_id'


LOGGER = logging.getLogger(__file__)


DBItem = namedtuple("DBItem", ['data', 'path'])


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


def create_id_dir(id_dir: Path, group: str, umask: int) -> (int, Path):
    """In the given directory, create the lowest numbered (positive integer)
    directory that doesn't already exist.

    :param id_dir: Path to the directory that contains these 'id'
        directories
    :param group: The group owner for this path.
    :param umask: The umask to apply to this path.
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

        with permissions.PermissionsManager(next_id_path, group, umask), \
                permissions.PermissionsManager(next_fn, group, umask):
            next_id_path.mkdir()
            with next_fn.open('w') as next_file:
                next_file.write(str(next_id + 1))

        return next_id, next_id_path


def default_filter(_: Path) -> bool:
    """Pass every path."""

    return True


Index = NewType("Index", Dict[int, Dict['str', Any]])


def index(id_dir: Path, idx_name: str,
          transform: Callable[[Path], Dict[str, Any]],
          complete_key: str = None,
          refresh_period: int = 2,
          fn_base: int = 10) -> Index:
    """Load and/or update an index of the given directory for the given
    transform, and return it. The returned index is a dictionary by id of
    the transformed data.

    :param id_dir: The directory to index.
    :param idx_name: The name of the index.
    :param transform: A transformation function that produces a json
        compatible dictionary.
    :param complete_key: The key in the transformed dictionary that marks a
        record as complete. If not given, the record is always assumed to be
        complete. Incomplete records are recompiled every time the index is
        updated (hopefully they will be complete eventually).
    :param refresh_period: Only update the index if this much time (in seconds)
        has passed since the last update.
    :param fn_base: The integer base for dir_db.
    """

    idx_path = (id_dir/idx_name).with_suffix('.idx')

    # Open and read the index if it exists. Any errors cause the index to
    # regenerate from scratch.
    if idx_path.exists():
        with idx_path.open() as idx_file:
            try:
                idx = json.load(idx_file)
                idx_stat = idx_path.stat()
            except (OSError, json.JSONDecodeError) as err:
                # In either error case, start from scratch.
                LOGGER.warning(
                    "Error reading index at '%s'. Regenerating from "
                    "scratch. %s", idx_path.as_posix(), err.args[0])
                idx = {}
    else:
        idx = {}

    # If the index hasn't been updated lately (or is empty) do so.
    # Small updates should happen unnoticeably fast, while full generation
    # will take a bit.
    if not idx or time.time() - idx_stat.st_mtime > refresh_period:
        seen = []

        for file in os.scandir(id_dir.as_posix()):

            # Only directories with integer names are db entries.
            if not file.is_dir():
                continue

            dir_ = Path(file)
            try:
                id_ = int(dir_.name, fn_base)
            except ValueError:
                continue

            seen.append(id_)

            # Skip entries that are known and complete.
            if id_ in idx and idx[id_].get(complete_key, True):
                continue

            # Update incomplete or unknown entries.
            try:
                idx[id_] = transform(dir_)
            except ValueError:
                continue

        # Delete entries that no longer exist.
        for id_ in list(idx.keys()):
            if id_ not in seen:
                del idx[id_]

        # Write our updated index atomically.
        tmp_path = idx_path.with_suffix(idx_path.suffix + '.tmp')
        with tmp_path.open('w') as tmp_file:
            json.dump(idx, tmp_file)
        tmp_path.rename(idx_path)

    return idx


def select(id_dir: Path,
           filter_func: Callable[[Any], bool] = default_filter,
           transform: Callable[[Path], Any] = lambda v: v,
           order_func: Callable[[Any], Any] = None,
           order_asc: bool = True,
           fn_base: int = 10,
           limit: int = None) -> (List[Any], List[Path]):
    """Takes the same arguments as 'select_from', except a directory to search
    from instead of a list of paths. Then picks from the files in that
    directory according to the given filter.

    :returns: A filtered, ordered list of transformed objects, and the list
              of untransformed paths.

    Other arguments are as per select_from."""

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
                limit: int = None) -> (List[Any], List[Path]):
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
    :returns: A filtered, ordered list of transformed objects, and the list
              of untransformed paths.
    """

    selected = []
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

        selected.append((item, path))

    if order_func is not None:
        selected.sort(key=lambda d: order_func(d[0]), reverse=not order_asc)

    return ([item[0] for item in selected][:limit],
            [item[1] for item in selected][:limit])


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


def delete(id_dir: Path, filter_func: Callable[[Path], bool] = default_filter,
           transform: Callable[[Path], Any] = lambda v: v,
           verbose: bool = False):
    """Delete all id directories in a given path that match the given filter.
    :param id_dir: The directory to iterate through.
    :param filter_func: A passed filter function, to be passed to select.
    :param transform: As per 'select_from'
    :param verbose: Verbose output.
    :return int count: The number of directories removed.
    :return list msgs: Any messages generated during removal.
    """

    count = 0
    msgs = []

    lock_path = id_dir.with_suffix('.lock')
    with lockfile.LockFile(lock_path, timeout=1):
        for path in select(id_dir=id_dir, filter_func=filter_func,
                           transform=transform)[1]:
            try:
                shutil.rmtree(path.as_posix())
            except OSError as err:
                msgs.append("Could not remove {} {}: {}"
                            .format(id_dir.name, path.as_posix(), err))
                continue
            count += 1
            if verbose:
                msgs.append("Removed {} {}.".format(id_dir.name, path.name))

    reset_pkey(id_dir)
    return count, msgs
