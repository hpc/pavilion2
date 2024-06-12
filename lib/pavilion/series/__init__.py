"""Module init for series objects and related functions."""

import json
from typing import TextIO

from pavilion import output
from pavilion import utils, dir_db
from ..sys_vars import base_classes
from ..errors import TestSeriesError, TestSeriesWarning
from .info import SeriesInfo, path_to_sid, mk_series_info_transform, TestSetInfo, SeriesInfoBase
from .series import TestSeries
from .test_set import TestSet
from .common import COMPLETE_FN, STATUS_FN, get_all_started


def load_user_series_id(pav_cfg, errfile=None):
    """Load the last series id used by the current user."""

    user = utils.get_login()
    last_series_fn = pav_cfg.working_dir/'users'
    last_series_fn /= '{}.json'.format(user)

    sys_vars = base_classes.get_vars(True)
    sys_name = sys_vars['sys_name']

    if not last_series_fn.exists():
        raise TestSeriesError("No known last series for user {} on host {}."
                              .format(user, sys_name))
    try:
        with last_series_fn.open() as last_series_file:
            sys_name_series_dict = json.load(last_series_file)
            return sys_name_series_dict[sys_name].strip()
    except (IOError, OSError, KeyError) as err:
        if errfile:
            output.fprint(errfile, "Failed to read series id file '{}'"
                                   .format(last_series_fn), err)
        return None


def list_series_tests(pav_cfg, sid: str):
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


def path_from_id(pav_cfg, sid: str):
    """Return the path to the series directory given a series id (in the
    format 's[0-9]+'.
    :raises TestSeriesError: For an invalid id.
    """

    if not sid.startswith('s'):
        raise TestSeriesError(
            "Series id's must start with 's'. Got '{}'".format(sid))

    try:
        raw_id = int(sid[1:])
    except ValueError:
        raise TestSeriesError(
            "Invalid series id '{}'. Series id's must be in the format "
            "s[0-9]+".format(sid))

    return dir_db.make_id_path(pav_cfg.working_dir/'series', raw_id)
