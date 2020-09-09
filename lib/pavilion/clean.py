
from pathlib import Path

from pavilion import builder
from pavilion import dir_db
from pavilion import utils


def delete_tests(pav_cfg, id_dir: Path, filter_func, verbose: bool=False):

    if filter_func is None:
        filter_func = dir_db.default_filter
        # Use default filter. This will likely remove every test dir.
        #return dir_db.delete(id_dir, verbose)
    return dir_db.delete(id_dir, filter_func, verbose)

def delete_series(id_dir: Path, verbose: bool=False) -> int:

    def filter_series(path: Path) -> bool:
        """Filter a series based on if it has any valid symlinked tests.
        :param path: This is the passed path object.
        :return True: The series dir can be removed.
        :return False: The series dir cannot be removed.
        """
        for test_path in path.iterdir():
            if (test_path.is_symlink() and
                test_path.exists() and
                utils.resolve_path(test_path).exists()):
                return False
        return True

    return dir_db.delete(id_dir, filter_series, verbose)

def delete_builds(builds_dir: Path, tests_dir: Path, verbose: bool=False):
    """Delete all build directories that are unused by any test run.
    :param builds_dir: Path to the pavilion builds directory.
    :param tests_dir: Path to the pavilion test_runs directory.
    :param verbose: Bool to determine if verbose output or not.
    """

    return builder.delete_unused(tests_dir, builds_dir, verbose)
