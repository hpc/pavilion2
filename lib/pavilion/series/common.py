"""Common functions and globals"""

from collections import UserDict
import json
import time
from pathlib import Path
from typing import Union

from pavilion import config
from pavilion import dir_db
from pavilion import status_file
from pavilion.test_run import TestRun
from pavilion.types import ID_Pair
from ..errors import TestSeriesError

COMPLETE_FN = 'SERIES_COMPLETE'
ALL_STARTED_FN = 'ALL_TESTS_STARTED'
STATUS_FN = 'status'
CONFIG_FN = 'config'


class LazyTestRunDict(UserDict):
    """A lazily evaluated dictionary of tests."""

    def __init__(self, pav_cfg):
        """Initialize the lazy TestRun dict."""

        self._pav_cfg = pav_cfg

        super().__init__()

    def add_key(self, id_pair: ID_Pair):
        """Add an ID_Pair key, but don't actually load the test."""

        self.data[id_pair] = None

    def __getitem__(self, id_pair: ID_Pair) -> TestRun:
        """When the item exists as a key but not a test object, load the test object."""

        if id_pair in self.data and self.data[id_pair] is None:
            working_dir, test_id = id_pair
            self.data[id_pair] = TestRun.load(self._pav_cfg, working_dir, test_id)

        return super().__getitem__(id_pair)


    def iter_paths(self):
        """An iterator over all test paths. (Run 'find_tests' first if unpopulated)"""

        for working_dir, test_id in self.keys():
            yield working_dir/'test_runs'/str(test_id)


    def by_test_set(self, series_path):
        """Return a dictionary of test paths



    def find_tests(self, series_path: Path):
        """Find all the tests for the series and add their keys."""


        # Handle both legacy series directories (all test links in series path)
        # and test_set organized series (all test links in test set dirs under '<series>/test_sets')
        test_sets_dir = series_path/'test_sets'
        if test_sets_dir.exists():
            search_dirs = test_sets_dir.iterdir()
        else:
            search_dirs = [series_path]

        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue

            for path in dir_db.select(self._pav_cfg, search_dir, use_index=False).paths:
                if not path.is_symlink():
                    continue

                try:
                    test_id = int(path.name)
                except ValueError:
                    continue

                try:
                    working_dir = path.resolve().parents[1]
                except FileNotFoundError:
                    continue

                self.add_key(ID_Pair((working_dir, test_id)))


def set_all_started(path: Path):
    """Touch the 'all_started' file, indicating that all tests that will be created
    by this series have been created."""

    all_started_fn = path/ALL_STARTED_FN

    try:
        if not all_started_fn.exists():
            all_started_fn.touch()
    except OSError:
        pass


# This is needed by both the series object and the series info object.
def set_complete(path, when: float = None):
    """Write a file in the series directory that indicates that the series
    has finished."""

    complete_fn = path/COMPLETE_FN
    status_fn = path/STATUS_FN

    series_status = status_file.SeriesStatusFile(status_fn)
    if not complete_fn.exists():
        if when is None:
            when = time.time()

        series_status.set(status_file.SERIES_STATES.COMPLETE, "Series has completed.")
        complete_fn_tmp = complete_fn.with_suffix('.tmp')
        try:
            with complete_fn_tmp.open('w') as series_complete:
                json.dump({'complete': when}, series_complete)
        except (OSError, ValueError) as err:
            raise TestSeriesError("Error saving completion file.", err)

        complete_fn_tmp.rename(complete_fn)


# If all tests in a series were completed more than this many seconds ago,
# Call the series complete even if it wasn't marked as such.
SERIES_COMPLETE_TIMEOUT = 3


def check_complete(pav_cfg: config.PavConfig, series_path: Path) -> bool:
    """Check whether all the the tests in the given series are complete. """

    if (series_path/COMPLETE_FN).exists():
        return True

    latest = None
    for test_path in dir_db.select(pav_cfg, series_path).paths:
        complete_file_path: Path = test_path / TestRun.COMPLETE_FN
        if not complete_file_path.exists():
            return False

        file_stat = complete_file_path.stat()
        if latest is None or latest < file_stat.st_mtime:
            latest = file_stat.st_mtime

    if (series_path/ALL_STARTED_FN).exists():
        return True

    if latest is not None and latest - time.time() > SERIES_COMPLETE_TIMEOUT:
        return True
    else:
        return False


def get_complete(pav_cfg: config.PavConfig, series_path: Path,
                 check_tests: bool = False) -> Union[dict, None]:
    """Get the series completion timestamp. Returns None when not complete.

    :param pav_cfg: Pavilion configuration
    :param series_path: Path to the series
    :param check_tests: Check tests for completion and set completion if all
        tests are complete. Will catch and ignore errors when setting completion.
    """

    complete_fn = series_path/COMPLETE_FN
    if complete_fn.exists():
        try:
            with complete_fn.open() as complete_file:
                return json.load(complete_file)
        except (OSError, json.decoder.JSONDecodeError):
            return None

    if check_tests:
        if check_complete(pav_cfg, series_path):
            now = time.time()
            try:
                set_complete(series_path, now)
            except TestSeriesError:
                return {'when': now}

    return None
