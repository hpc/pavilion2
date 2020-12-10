"""Provides utility functions for deleting Pavilion working_dir files."""
import shutil
from pathlib import Path
from typing import List

from pavilion import dir_db
from pavilion import lockfile
from pavilion import test_run
from pavilion import utils
from pavilion.builder import TestBuilder


def delete_tests(id_dir: Path, filter_func, verbose: bool = False):
    """Delete tests using the dir_db 'filter' function"""

    if filter_func is None:
        filter_func = dir_db.default_filter
    return dir_db.delete(id_dir, filter_func,
                         transform=test_run.TestAttributes,
                         verbose=verbose)


def delete_series(id_dir: Path, verbose: bool = False) -> int:
    """Delete series if all associated tests have been deleted."""

    def filter_series(path: Path) -> bool:
        """True if the series does not have any valid symlinked tests."""

        for test_path in path.iterdir():
            if (test_path.is_symlink() and
                    test_path.exists() and
                    utils.resolve_path(test_path).exists()):
                return False

        return True

    return dir_db.delete(id_dir, filter_series, verbose=verbose)


def delete_builds(builds_dir: Path, tests_dir: Path, verbose: bool = False):
    """Delete all build directories that are unused by any test run.
    :param builds_dir: Path to the pavilion builds directory.
    :param tests_dir: Path to the pavilion test_runs directory.
    :param verbose: Bool to determine if verbose output or not.
    """

    return delete_unused(tests_dir, builds_dir, verbose)


def delete_unused(tests_dir: Path, builds_dir: Path, verbose: bool = False) \
        -> (int, List[str]):
    """Delete all the build directories, that are unused by any test run.

    :param tests_dir: The test_runs directory path object.
    :param builds_dir: The builds directory path object.
    :param verbose: Print

    :return int count: The number of builds that were removed.

    """

    used_build_paths = _get_used_build_paths(tests_dir)

    def filter_builds(build_path: Path) -> bool:
        """Return whether a build is not used."""
        return build_path.name not in used_build_paths

    count = 0

    lock_path = builds_dir.with_suffix('.lock')
    msgs = []
    with lockfile.LockFile(lock_path) as lock:
        for path in dir_db.select(builds_dir, filter_builds, fn_base=16)[0]:
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


def _get_used_build_paths(tests_dir: Path) -> set:
    """Generate a set of all build paths currently used by one or more test
    runs."""

    used_builds = set()

    for path in dir_db.select(tests_dir)[0]:
        build_origin_symlink = path/'build_origin'
        build_origin = None
        if (build_origin_symlink.exists() and
                build_origin_symlink.is_symlink() and
                utils.resolve_path(build_origin_symlink).exists()):
            build_origin = build_origin_symlink.resolve()

        if build_origin is not None:
            used_builds.add(build_origin.name)

    return used_builds
