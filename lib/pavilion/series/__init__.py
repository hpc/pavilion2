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


from .utils import list_series_tests, path_from_id
