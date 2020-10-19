"""Provides utility functions for deleting Pavilion working_dir files."""

from pathlib import Path

from pavilion import builder
from pavilion import dir_db
from pavilion import utils
from pavilion import test_run


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
        """Return True if the series does not have any valid symlinked tests.
        """
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

    return builder.delete_unused(tests_dir, builds_dir, verbose)
