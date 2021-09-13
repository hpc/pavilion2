"""Manage 'id' directories. The name of the directory is an integer, which
essentially serves as a filesystem primary key."""

import dbm
import json
import logging
import os
import shutil
import tempfile
import time
import multiprocessing as mp
from functools import partial
from pathlib import Path
from typing import Callable, List, Iterable, Any, Dict, NewType, \
    Union, NamedTuple, IO

from pavilion import config
from pavilion import lockfile
from pavilion import output
from pavilion import permissions

ID_DIGITS = 7
ID_FMT = '{id:0{digits}d}'

PKEY_FN = 'next_id'


LOGGER = logging.getLogger(__file__)


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


def identity(value):
    """Because lambdas can't be pickled."""
    return value


def index(id_dir: Path, idx_name: str,
          transform: Callable[[Path], Dict[str, Any]],
          complete_key: str = 'complete',
          refresh_period: int = 1,
          remove_missing: bool = False,
          verbose: IO[str] = None,
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
    :param remove_missing: Remove items that no longer exist from the index.
    :param fn_base: The integer base for dir_db.
    """

    idx_path = (id_dir/idx_name).with_suffix('.db')

    idx = Index({})
    idx_db = None

    # Open and read the index if it exists. Any errors cause the index to
    # regenerate from scratch.
    idx_mtime = 0
    if idx_path.exists():
        try:
            idx_db = dbm.open(idx_path.as_posix())
            idx_mtime = idx_path.stat().st_mtime
            idx = Index({int(k): json.loads(idx_db[k]) for k in idx_db.keys()})
        except (OSError, PermissionError, json.JSONDecodeError) as err:
            # In either error case, start from scratch.
            LOGGER.warning(
                "Error reading index at '%s'. Regenerating from "
                "scratch. %s", idx_path.as_posix(), err.args[0])

    new_items = {}

    # If the index hasn't been updated lately (or is empty) do so.
    # Small updates should happen unnoticeably fast, while full generation
    # will take a bit.
    if not idx or time.time() - idx_mtime > refresh_period:
        seen = []

        if verbose:
            if idx_db is None:
                output.fprint(
                    "No index file found for '{}'. This may take a while."
                    .format(id_dir.name),
                    file=verbose)

        last_perc = None
        progress = 0

        files = list(os.scandir(id_dir.as_posix()))
        for file in files:
            try:
                id_ = int(file.name, fn_base)
            except ValueError:
                continue

            seen.append(id_)

            progress += 1
            complete_perc = int(100*progress/len(files))
            if verbose and complete_perc != last_perc:
                output.fprint(
                    "Indexing: {}%".format(complete_perc),
                    end='\r', file=verbose)
                last_perc = complete_perc

            # Skip entries that are known and complete.
            if id_ in idx and idx[id_].get(complete_key, False):
                continue

            # Only directories with integer names are db entries.
            if not file.is_dir():
                continue

            # Update incomplete or unknown entries.
            try:
                new = transform(Path(file.path))
            except ValueError:
                continue

            old = idx.get(id_)
            if new != old:
                new_items[id_] = new
                idx[id_] = new

        missing = set(idx.keys()) - set(seen)

        if new_items or missing:
            try:
                group = idx_path.parent.stat().st_gid
                tmp_path = Path(tempfile.mktemp(
                    suffix='.dbtmp',
                    dir=idx_path.parent.as_posix()))
                if idx_path.exists():
                    try:
                        shutil.copyfile(idx_path, tmp_path.as_posix())
                    except OSError:
                        pass

                # Write our updated index atomically.
                with permissions.PermissionsManager(tmp_path,
                                                    group, 0o002):
                    out_db = dbm.open(tmp_path.as_posix(), 'c')

                    for id_, value in new_items.items():
                        out_db[str(id_)] = json.dumps(value)

                    for id_ in missing:

                        del out_db[str(id_)]
                        del idx[id_]

                tmp_path.rename(idx_path)
            except OSError:
                pass

    return idx


SelectItems = NamedTuple("SelectItems", [('data', List[Dict[str, Any]]),
                                         ('paths', List[Path])])

def select_one(path, ffunc, trans, ofunc, fnb):
    """Allows the objects to be filtered and transformed in parallel with map.

    :param path: Path to filter and transform (input to reduced function)
    :param ffunc: (filter function) Function that takes a directory, and returns
        whether to include that directory. True -> include, False -> exclude
    :param trans: Function to apply to each path before applying filters
        or ordering. The filter and order functions should expect the type
        returned by this.
    :param ofunc: A function that returns a comparable value for sorting
        validate against output.
    :param fnb: Number base for file names. 10 by default, ensure dir name
        is a valid integer.
    :returns: A filtered, transformed object.
    """

    if trans is None:
        trans = identity

    if not path.is_dir():
        return None
    try:
        int(path.name, fnb)
        item = trans(path)
    except ValueError:
        return None

    if not ffunc(item):
        return None

    if ofunc is not None and ofunc(item) is None:
        return None

    return item


def select(id_dir: Path,
           filter_func: Callable[[Any], bool] = default_filter,
           transform: Callable[[Path], Any] = None,
           order_func: Callable[[Any], Any] = None,
           order_asc: bool = True,
           fn_base: int = 10,
           idx_complete_key: 'str' = 'complete',
           use_index: Union[bool, str] = True,
           verbose: IO[str] = None,
           limit: int = None) -> (List[Any], List[Path]):
    """Filter and order found paths in the id directory based on the filter and
    other parameters. If a transform is given, this will create an index of the
    data returned by the transform to hasten this process.

    :param id_dir: The director
    :param transform: Function to apply to each path before applying filters
        or ordering. The filter and order functions should expect the type
        returned by this.
    :param filter_func: A function that takes a directory, and returns whether
        to include that directory. True -> include, False -> exclude
    :param order_func: A function that returns a comparable value for sorting,
        as per the list.sort keys argument. Items for which this returns
        None are removed.
    :param order_asc: Whether to sort in ascending or descending order.
    :param use_index: The name of (and whether to use) an index. When this is
        the literal 'True', the index name is pulled from the transform
        function name. A string can also be given to manually specify the name.
    :param idx_complete_key: The key used to identify directories as 'complete'
        for indexing purposes. Incomplete directories will be re-indexed until
        complete.
    :param fn_base: Number base for file names. 10 by default, ensure dir name
        is a valid integer.
    :param limit: The max items to return. None denotes return all.
    :param verbose: A file like object to print status info to.
    :returns: A filtered, ordered list of transformed objects, and the list
              of untransformed paths.
    """
    if transform and use_index:
        # Bwahaha - I'm checking that use_index is actually the singleton True,
        # not anything else that might evaluate to True.
        if use_index is True:
            index_name = transform.__name__
        else:
            index_name = use_index

        if index_name == '<lambda>':
            raise RuntimeError(
                "You must provide an index name using the 'use_index' "
                "parameter when using a lambda function as the transform.")

        selected = []

        idx = index(id_dir, index_name, transform,
                    complete_key=idx_complete_key,
                    verbose=verbose)
        for id_, data in idx.items():
            path = make_id_path(id_dir, id_)

            if order_func is not None and order_func(data) is None:
                continue

            if not filter_func(data):
                continue

            selected.append((data, path))

        if order_func is not None:
            selected.sort(key=lambda d: order_func(d[0]), reverse=not order_asc)

        return SelectItems(
                [item[0] for item in selected][:limit],
                [item[1] for item in selected][:limit])
    else:
        return select_from(
            paths=id_dir.iterdir(),
            transform=transform,
            filter_func=filter_func,
            order_func=order_func,
            order_asc=order_asc,
            fn_base=fn_base,
            limit=limit)


def select_from(paths: Iterable[Path],
                filter_func: Callable[[Any], bool] = default_filter,
                transform: Callable[[Path], Any] = None,
                order_func: Callable[[Any], Any] = None,
                order_asc: bool = True,
                fn_base: int = 10,
                limit: int = None) -> (List[Any], List[Path]):
    """Filter, order, and truncate the given paths based on the filter and
    other parameters.

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

    paths = list(paths)
    ncpu = min(config.NCPU, len(paths))
    mp_pool = mp.Pool(processes=ncpu)

    selector = partial(select_one, ffunc=filter_func, trans=transform,
                                   ofunc=order_func, fnb=fn_base)

    selections = mp_pool.map(selector, paths)
    selected = [(item,path) for item, path in zip(selections,paths) if item is not None]

    if order_func is not None:
        selected.sort(key=lambda d: order_func(d[0]), reverse=not order_asc)

    return SelectItems(
        [item[0] for item in selected][:limit],
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
           transform: Callable[[Path], Any] = None,
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
                           transform=transform).paths:
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
