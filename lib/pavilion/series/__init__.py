"""Module init for series objects and related functions."""

import json
from pathlib import Path
from typing import TextIO, Optional, List

from pavilion import output
from pavilion import utils, dir_db
from pavilion.config import PavConfig
from pavilion.test_ids import SeriesID
from ..errors import TestSeriesError, TestSeriesWarning
from .info import SeriesInfo, path_to_sid, mk_series_info_transform, TestSetInfo, SeriesInfoBase
from .series import TestSeries
from .test_set import TestSet
from .common import COMPLETE_FN, STATUS_FN, get_all_started


def list_series_tests(pav_cfg, sid: SeriesID) -> List[Path]:
    """Return a list of paths to test run directories for the given series id.
    :raises TestSeriesError: If the series doesn't exist."""

    series_path = path_from_id(pav_cfg, sid)

    if not series_path.exists():
        raise TestSeriesError(
            "No such test series '{}'. Looked in {}."
            .format(sid, series_path))

    test_paths = []
    test_set_path = series_path/'test_sets'
    if test_set_path.exists():
        for test_set in test_set_path.iterdir():
            if not test_set.is_dir():
                continue

            test_paths.extend(dir_db.select(pav_cfg, test_set).paths)
    else:
        test_paths.extend(dir_db.select(pav_cfg, series_path).paths)

    return test_paths


def path_from_id(pav_cfg: PavConfig, sid: SeriesID) -> Path:
    """Return the path to the series directory given a series id (in the
    format 's[0-9]+'.
    :raises TestSeriesError: For an invalid id.
    """

    return pav_cfg.working_dir / "series" / str(sid.as_int())
