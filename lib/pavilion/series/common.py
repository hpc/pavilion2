"""Common functions and globals"""

import json
import time
from pathlib import Path
from typing import Union

from pavilion import config
from pavilion import dir_db
from pavilion import status_file
from pavilion.test_run import TestRun

COMPLETE_FN = 'SERIES_COMPLETE'
STATUS_FN = 'status'


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
        with complete_fn_tmp.open('w') as series_complete:
            json.dump({'complete': when}, series_complete)

        complete_fn_tmp.rename(complete_fn)


# If all tests in a series were completed more than this many seconds ago,
# Call the series complete even if it wasn't marked as such.
SERIES_COMPLETE_TIMEOUT = 3


def get_complete(pav_cfg: config.PavConfig, series_path: Path,
                 check_tests: bool = False) -> Union[dict, None]:
    """Get the series completion timestamp. Returns None when not complete.

    :param pav_cfg: Pavilion configuration
    :param series_path: Path to the series
    :param check_tests: Check tests for completion and set completion if all
        tests are complete.
    """

    complete_fn = series_path/COMPLETE_FN
    if complete_fn.exists():
        try:
            with complete_fn.open() as complete_file:
                return json.load(complete_file)
        except (OSError, json.decoder.JSONDecodeError):
            return None

    if check_tests:
        latest = None
        for test_path in dir_db.select(pav_cfg, series_path).paths:
            complete_file_path: Path = test_path/TestRun.COMPLETE_FN
            if not complete_file_path.exists():
                return None

            file_stat = complete_file_path.stat()
            if latest is None or latest < file_stat.st_mtime:
                latest = file_stat.st_mtime

        if latest is not None and latest - time.time() > SERIES_COMPLETE_TIMEOUT:
            set_complete(series_path, latest)
            return {'when': latest}

    return None
