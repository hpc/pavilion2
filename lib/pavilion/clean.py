
from pathlib import Path

from pavilion import builder
from pavilion import dir_db


def delete_tests(pav_cfg, id_dir: Path, filter_func, verbose: bool=False):

    if filter_func is None:
        # Use default filter. This will likely remove every test dir.
        return dir_db.delete(id_dir, verbose)
    return dir_db.delete(id_dir, filter_func, verbose)

def delete_series(id_dir: Path, filter_func, verbose: bool=False) -> int:

    if filter_func is None:
        # Use default filter. This will likely remove every series dir.
        return dir_db.delete(id_dir, verbose)

    return dir_db.delete(id_dir, filter_func, verbose)

def delete_builds(builds_dir: Path, tests_dir: Path, verbose: bool=False):
    """Delete all build directories that are unused by any test run.
    :param builds_dir: Path to the pavilion builds directory.
    :param tests_dir: Path to the pavilion test_runs directory.
    :param verbose: Bool to determine if verbose output or not.
    """

    return builder.delete_unused(tests_dir, builds_dir, verbose)
