"""Manage 'id' directories. The name of the directory is an integer, which
essentially serves as a filesystem primary key."""

import json
import logging
import math
import os
import pickle
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from pathlib import Path
from typing import Callable, List, Iterable, Any, Dict, NewType, \
    Union, NamedTuple, IO, Tuple

from pavilion import lockfile
from pavilion import output

ID_DIGITS = 7
ID_FMT = '{id:d}'

PKEY_FN = 'next_id'


LOGGER = logging.getLogger(__file__)


def make_id_path(base_path, id_) -> Path:
    """Create the full path to an id directory given its base path and
    the id.

    :param Path base_path: The path to where id directories are stored.
    :param int id_: The id number
    :rtype: Path
    """

    return base_path / (ID_FMT.format(id=id_))


def reset_pkey(id_dir: Path) -> None:
    """Reset the the 'next_id' for the given directory by deleting
    the pkey file ('next_id') if present."""

    try:
        with lockfile.LockFile(id_dir/'.lockfile', timeout=1):
            try:
                (id_dir/PKEY_FN).unlink()
            except OSError:
                pass
    except TimeoutError:
        pass


def create_id_dir(id_dir: Path) -> (int, Path):
    """In the given directory, create the lowest numbered (positive integer)
    directory that doesn't already exist.

    :param id_dir: Path to the directory that contains these 'id'
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


Index = NewType("Index", Dict[int, Dict['str', Any]])


def identity(value):
    """Because lambdas can't be pickled."""
    return value


def index(pav_cfg,
          id_dir: Path, idx_name: str,
          transform: Callable[[Path], Dict[str, Any]],
          complete_key: str = 'complete',
          refresh_period: int = 1,
          verbose: IO[str] = None,
          fn_base: int = 10) -> Index:
    """Load and/or update an index of the given directory for the given
    transform, and return it. The returned index is a dictionary by id of
    the transformed data.

    :param pav_cfg: The pavilion config.
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
    :param verbose: Print status information during indexing.
    :param fn_base: The integer base for dir_db.
    """

    idx_path = (id_dir/idx_name).with_suffix('.pkl')

    idx = Index({})

    # Open and read the index if it exists. Any errors cause the index to
    # regenerate from scratch.
    idx_mtime = 0
    if idx_path.exists():
        try:
            with idx_path.open('rb') as idx_file:
                idx = pickle.load(idx_file)
        except (OSError, PermissionError, json.JSONDecodeError) as err:
            # In either error case, start from scratch.
            output.fprint(verbose, "Error reading index at '{}'. Regenerating from "
                                   "scratch. {}".format(idx_path.as_posix(), err),
                          color=output.GRAY)

    if not id_dir.exists():
        return idx

    if idx and time.time() - idx_mtime <= refresh_period:
        return idx

    files = [file.path for file in os.scandir(id_dir.as_posix())]

    def make_int_ids(paths: List[Path]) -> List[Tuple[int, Path]]:
        """Convert an filename to an integer if we can."""

        id_results = []

        for id_path in paths:
            id_path = Path(id_path)

            try:
                id_results.append((int(id_path.name, fn_base), id_path))
            except ValueError:
                pass

        return id_results

    def do_transform(pair):
        """Do the transform on the id and file pair."""

        tid, file = pair

        try:
            return tid, transform(file)
        except (ValueError, KeyError, TypeError, OSError) as err:
            return tid, None

    thread_max = pav_cfg.get('max_threads')
    with ThreadPoolExecutor(max_workers=thread_max) as pool:
        # This sequence leaves us with a list of id, path pairs that need an index
        # update.
        chunk_size = int(math.ceil(len(files)/float(thread_max)))
        chunks = [files[i*chunk_size:(i+1)*chunk_size] for i in range(thread_max)]

        id_pairs = pool.map(make_int_ids, chunks)
        # Grab the set of all ids. We'll use it to identify missing ids.
        all_seen_ids = set()
        update_id_pairs = []
        for chunked_results in id_pairs:
            for id_, path in chunked_results:
                if id_ is None:
                    continue

                all_seen_ids.add(id_)

                if id_ in idx and idx[id_].get(complete_key, False):
                    continue
                update_id_pairs.append((id_, path))

        missing = set(idx.keys()) - all_seen_ids

        transformed_data = pool.map(do_transform, update_id_pairs)

    for id_, data in transformed_data:
        if data is None:
            continue

        idx[id_] = data

    for id_ in missing:
        del idx[id_]

    tmp_path = Path(tempfile.mktemp(
        suffix='.dbtmp',
        dir=idx_path.parent.as_posix()))
    try:
        with tmp_path.open('wb') as tmp_file:
            pickle.dump(idx, tmp_file)
        tmp_path.rename(idx_path)
    except OSError:
        return idx
    except (Exception, KeyboardInterrupt) as err:
        try:
            tmp_path.unlink()
        except OSError:
            pass
        raise err

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


def select(pav_cfg,
           id_dir: Path,
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

    :param pav_cfg: The pavilion config.
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

        idx = index(pav_cfg, id_dir, index_name, transform,
                    complete_key=idx_complete_key, verbose=verbose)
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
            pav_cfg,
            paths=id_dir.iterdir(),
            transform=transform,
            filter_func=filter_func,
            order_func=order_func,
            order_asc=order_asc,
            fn_base=fn_base,
            limit=limit)


def select_from(pav_cfg,
                paths: Iterable[Path],
                filter_func: Callable[[Any], bool] = default_filter,
                transform: Callable[[Path], Any] = None,
                order_func: Callable[[Any], Any] = None,
                order_asc: bool = True,
                fn_base: int = 10,
                limit: int = None) -> (List[Any], List[Path]):
    """Filter, order, and truncate the given paths based on the filter and
    other parameters.

    :param pav_cfg: The pavilion config.
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
    max_threads = min(pav_cfg.get('max_threads', 1), len(paths))

    selector = partial(select_one, ffunc=filter_func, trans=transform,
                       ofunc=order_func, fnb=fn_base)

    if max_threads > 1:
        with ThreadPoolExecutor(max_workers=max_threads) as pool:
            selections = pool.map(selector, paths)
    else:
        selections = map(selector, paths)

    selected = [(item, path) for item, path in zip(selections, paths)
                if item is not None]

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


def delete(pav_cfg, id_dir: Path, filter_func: Callable[[Path], bool] = default_filter,
           transform: Callable[[Path], Any] = None,
           verbose: bool = False):
    """Delete all id directories in a given path that match the given filter.

    :param pav_cfg: The pavilion config.
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
    try:
        with lockfile.LockFile(lock_path, timeout=1):
            for path in select(pav_cfg, id_dir=id_dir, filter_func=filter_func,
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
    except TimeoutError as err:
        msgs.append("Could not delete in dir '{}', lock '{}' could not be acquired"
                    .format(id_dir, lock_path))

    reset_pkey(id_dir)
    return count, msgs
