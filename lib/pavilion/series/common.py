"""Common functions and globals"""

from collections import UserDict
import json
import os
import time
from pathlib import Path
from typing import Union

from pavilion import config
from pavilion import dir_db
from pavilion import status_file
from pavilion.test_run import TestRun, TestAttributes
from pavilion.types import ID_Pair
from ..errors import TestSeriesError

COMPLETE_FN = 'SERIES_COMPLETE'
ALL_STARTED_FN = 'ALL_TESTS_STARTED'
STATUS_FN = 'status'
CONFIG_FN = 'config'


class LazyTestRunDict(UserDict):
    """A lazily evaluated dictionary of tests."""

    def __init__(self, pav_cfg: config.PavConfig, series_path: Path):
        """Initialize the lazy TestRun dict."""

        self._pav_cfg = pav_cfg
        self._path = series_path

        super().__init__()

    def add_key(self, id_pair: ID_Pair):
        """Add an ID_Pair key, but don't actually load the test."""

        self.data[id_pair] = None

    def __getitem__(self, id_pair: ID_Pair) -> TestRun:
        """When the item exists as a key but not a test object, load the test object."""

        if not self.data:
            self.find_tests()

        if id_pair in self.data and self.data[id_pair] is None:
            working_dir, test_id = id_pair
            self.data[id_pair] = TestRun.load(self._pav_cfg, working_dir, test_id)

        return super().__getitem__(id_pair)

    def keys(self):
        """Return an iterator over the keys of this dict."""

        if not self.data:
            self.find_tests()

        for key in self.data:
            yield key

    def values(self):
        """Return an iterator over the values of this dict."""

        for key in self.keys():
            yield self[key]

    def iter_paths(self):
        """An iterator over all test paths. (Run 'find_tests' first if unpopulated)"""

        if not self.data:
            self.find_tests()

        for working_dir, test_id in self.keys():
            yield working_dir/'test_runs'/str(test_id)

    def find_tests(self):
        """Find all the tests for the series and add their keys."""

        # Handle both legacy series directories (all test links in series path)
        # and test_set organized series (all test links in test set dirs under '<series>/test_sets')
        test_sets_dir = self._path/'test_sets'
        if test_sets_dir.exists():
            search_dirs = test_sets_dir.iterdir()
        else:
            search_dirs = [self._path]

        for search_dir in search_dirs:
            if not search_dir.is_dir():
                continue

            for path in search_dir.iterdir():
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


def get_all_started(path: Path) -> Union[float, None]:
    """Return the timestamp of the 'all_started' file, or None if it doesn't exist."""

    return (path/ALL_STARTED_FN).exists()


# This is needed by both the series object and the series info object.
def set_complete(path, when: float = None) -> dict:
    """Write a file in the series directory that indicates that the series
    has finished."""

    complete_fn = path/COMPLETE_FN
    status_fn = path/STATUS_FN

    if when is None:
        when = time.time()

    complete_data = {'complete': when}

    series_status = status_file.SeriesStatusFile(status_fn)
    if not complete_fn.exists():

        state = series_status.current().state
        if 'ERROR' not in state:
            series_status.set(status_file.SERIES_STATES.COMPLETE, "Series has completed.")

        complete_fn_tmp = complete_fn.with_suffix('.tmp')
        try:
            with complete_fn_tmp.open('w') as series_complete:
                json.dump(complete_data, series_complete)
        except (OSError, ValueError) as err:
            raise TestSeriesError("Error saving completion file.", err)

        complete_fn_tmp.rename(complete_fn)

    # Note that this might be a bit off from reality if something else set the
    # complete time, but it will be close enough.
    return complete_data


# If all tests in a series were completed more than this many seconds ago,
# Call the series complete even if it wasn't marked as such.
SERIES_COMPLETE_TIMEOUT = 3*60*60

def _read_complete(series_path: Path) -> Union[dict, None]:
    """Read the series completion file, if it exists, and return the completion data.
    Returns None if the completion file doesn't exist or can't be read."""

    complete_fn = series_path/COMPLETE_FN
    if complete_fn.exists():
        try:
            with complete_fn.open() as complete_file:
                return json.load(complete_file)
        except (OSError, json.decoder.JSONDecodeError):
            return None


def get_complete(pav_cfg: config.PavConfig, series_path: Path,
                 check_tests: bool = False) -> Union[dict, None]:
    """Check whether all the test sets in a series are complete.
    :param check_tests: Check tests for completion and set completion if all
        tests are complete. Will catch and ignore errors when setting completion."""

    if (series_path/COMPLETE_FN).exists():
        return _read_complete(series_path)

    if not (series_path/'test_sets').exists():
        return None

    latest = None
    # Get the latest completion time for each test set
    # I any test set isn't complete, we're not done.
    for test_set_path in (series_path/'test_sets').iterdir():
        if not test_set_path.is_dir():
            continue

        ts_complete = get_test_set_complete(pav_cfg, test_set_path, check_tests)
        if ts_complete is None:
            return None

        if latest is None or latest < ts_complete:
            latest = ts_complete

    if latest and (series_path/ALL_STARTED_FN).exists():
        # All tests exist, so now it's just a matter of waiting for all test sets
        # to complete (which they have if we're at this point)
        set_complete(series_path, latest)
        return latest

    if latest is None:
        try:
            latest = series_path.stat().st_mtime
        except OSError:
            return None

    # Set the series as complete if the last test set completed a while ago.
    # There's no guarantee at this point that all test sets have even
    # been created though.
    if latest + SERIES_COMPLETE_TIMEOUT < time.time():
        set_complete(series_path, latest)
        return latest

    return None

def set_test_set_complete(test_set_path: Path, when: float):
    """Create a test set completion file and set it's timestamp."""

    complete_fn = test_set_path/COMPLETE_FN
    if not complete_fn.exists():
        try:
            complete_fn.touch()
            os.utime(complete_fn.as_posix(), (when, when))
        except OSError:
            pass


def get_test_set_complete(pav_cfg: config.PavConfig, test_set_path: Path,
                 check_tests: bool = False) -> Union[float, None]:
    """Get the test set completion timestamp. Returns None when not complete.

    :param pav_cfg: Pavilion configuration
    :param series_path: Path to the series
    :param check_tests: Check tests for completion and set completion if all
        tests are complete. Will catch and ignore errors when setting completion.
    """

    complete_fn = test_set_path/COMPLETE_FN
    if complete_fn.exists():
        try:
            return complete_fn.stat().st_mtime
        except OSError:
            return None

    if check_tests:
        latest = None
        for test_path in dir_db.select(pav_cfg, test_set_path).paths:
            complete_ts = TestAttributes(test_path).complete_time

            if complete_ts is None:
                return None

            if latest is None or complete_ts > latest:
                latest = complete_ts

        if latest is not None and latest + SERIES_COMPLETE_TIMEOUT < time.time():
            set_test_set_complete(test_set_path, latest)


        return latest
    else:
        return None
