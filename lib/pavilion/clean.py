"""Provides utility functions for deleting Pavilion working_dir files."""
import shutil
from functools import partial
from pathlib import Path
from typing import List

from pavilion import dir_db
from pavilion import lockfile
from pavilion import utils
from pavilion.builder import TestBuilder
from pavilion.test_run import test_run_attr_transform


def delete_tests(pav_cfg, id_dir: Path, filter_func, verbose: bool = False):
    """Delete tests using the dir_db 'filter' function"""

    if filter_func is None:
        filter_func = dir_db.default_filter
    return dir_db.delete(pav_cfg, id_dir, filter_func,
                         transform=test_run_attr_transform,
                         verbose=verbose)


def _delete_series_filter(path: Path) -> bool:
    """True if the series does not have any valid symlinked tests."""

    for test_path in path.iterdir():
        if (test_path.is_symlink() and
                test_path.exists() and
                utils.resolve_path(test_path).exists()):
            return False

    return True


def delete_series(pav_cfg, id_dir: Path, verbose: bool = False) -> int:
    """Delete series if all associated tests have been deleted."""

    return dir_db.delete(pav_cfg, id_dir, _delete_series_filter, verbose=verbose)


def delete_builds(pav_cfg, builds_dir: Path, tests_dir: Path, verbose: bool = False):
    """Delete all build directories that are unused by any test run.

    :param pav_cfg: The pavilion config.
    :param builds_dir: Path to the pavilion builds directory.
    :param tests_dir: Path to the pavilion test_runs directory.
    :param verbose: Bool to determine if verbose output or not.
    """

    return delete_unused(pav_cfg, tests_dir, builds_dir, verbose)


def _filter_unused_builds(used_build_paths: List[Path], build_path: Path) -> bool:
    """Return whether a build is not used."""
    return build_path.name not in used_build_paths


def delete_unused(pav_cfg, tests_dir: Path, builds_dir: Path, verbose: bool = False) \
        -> (int, List[str]):
    """Delete all the build directories, that are unused by any test run.

    :param pav_cfg: The pavilion config.
    :param tests_dir: The test_runs directory path object.
    :param builds_dir: The builds directory path object.
    :param verbose: Print

    :return int count: The number of builds that were removed.

    """

    used_build_paths = _get_used_build_paths(pav_cfg, tests_dir)

    filter_builds = partial(_filter_unused_builds, used_build_paths)

    count = 0

    lock_path = builds_dir.with_suffix('.lock')
    msgs = []
    with lockfile.LockFile(lock_path) as lock:
        for path in dir_db.select(pav_cfg, builds_dir, filter_builds, fn_base=16)[0]:
            lock.renew()
            try:
                shutil.rmtree(path.as_posix())
                path.with_suffix(TestBuilder.FINISHED_SUFFIX).unlink()
            except OSError as err:
                msgs.append("Could not remove build {}: {}"
                            .format(path, err))
                continue
            count += 1
            if verbose:
                msgs.append('Removed build {}.'.format(path.name))

    return count, msgs


def _get_used_build_paths(pav_cfg, tests_dir: Path) -> set:
    """Generate a set of all build paths currently used by one or more test
    runs."""

    used_builds = set()

    for path in dir_db.select(pav_cfg, tests_dir).paths:
        build_origin_symlink = path/'build_origin'
        build_origin = None
        if (build_origin_symlink.exists() and
                build_origin_symlink.is_symlink() and
                utils.resolve_path(build_origin_symlink).exists()):
            build_origin = build_origin_symlink.resolve()

        if build_origin is not None:
            used_builds.add(build_origin.name)

    return used_builds


def delete_lingering_build_files(pav_cfg, build_dir: Path, tests_dir: Path,
                                 verbose: bool = False):
    """
    Delete any lingering build related files that don't get handled in
    delete_builds. Mainly used to remove .lock and .log files that are
    associated with build hash dirs that do not exist.

    :param pav_cfg: The pavilion config.
    :param build_dir:  Path to the pavilion builds directory.
    :param tests_dir: Path to the pavilion test_runs directory.
    :param verbose: Print output
    """

    # Avoid anything that matches build hash in this list
    used_build_paths = _get_used_build_paths(pav_cfg, tests_dir)

    msgs = []
    for path in build_dir.iterdir():
        # Not responsible for deleting build hash directories.
        if path.is_dir():
            continue
        # Don't remove anything associated with a used build hash.
        if path.stem in used_build_paths:
            continue

        # Only remove .lock and .log files.
        if path.name.endswith(".lock") or path.name.endswith(".log"):
            path.unlink()
            if verbose:
                msgs.append("Removed lingering build file {}."
                            .format(path.name))

    return msgs
