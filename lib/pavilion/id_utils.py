"""Utilities for working with test, series, and group IDs.

I'm putting this in its own file because it causes a circular import pretty much anywhere
else I try to put it. – HW"""

import json
from pathlib import Path
from typing import TextIO, Optional

from pavilion import utils
from pavilion import output
from pavilion.config import PavConfig
from pavilion.sys_vars import base_classes
from pavilion.test_ids import SeriesID, TestID, TestIDError


def load_user_series_id(pav_cfg: PavConfig, errfile: TextIO = None) -> Optional[SeriesID]:
    """Load the last series id used by the current user."""

    user = utils.get_login()
    last_series_fn = pav_cfg.working_dir/'users'
    last_series_fn /= '{}.json'.format(user)

    sys_vars = base_classes.get_vars(True)
    sys_name = sys_vars['sys_name']

    if not last_series_fn.exists():
        return None

    try:
        with last_series_fn.open() as last_series_file:
            sys_name_series_dict = json.load(last_series_file)
            return SeriesID(sys_name_series_dict[sys_name].strip())
    except (IOError, OSError, KeyError) as err:
        if errfile:
            output.fprint(errfile, "Failed to read series id file '{}'"
                                   .format(last_series_fn), err)
        return None

def resolve_relative_id(pav_cfg: PavConfig, working_dir: Path, test_id: TestID) -> TestID:
    """Resolve a series-relative ID into an absolute ID."""

    if test_id.is_absolute():
        return test_id

    if test_id.series is None:
        sid = load_user_series_id(pav_cfg)

        if sid is None:
            raise TestIDError(f"Unable to resolve test ID '{test_id}' with implicit series "
                            "'last'. No last series found.")

        test_id.series = sid

    series_dir = working_dir / "series" / str(test_id.series.as_int()) / "test_sets"

    if not series_dir.exists():
        raise TestIDError(f"Unable to resolve relative test ID '{test_id}' to absolute ID. "
                          f"No series '{test_id.series}' found.")

    # Search the series directory for the symlink matching the relative test ID, then resolve
    # it to the absolute test ID.
    for test_set in series_dir.iterdir():

        if not test_set.is_dir():
            continue

        for test in test_set.iterdir():
            if test.name == str(test_id.id):
                return TestID(test.resolve().name)

    raise TestIDError(f"Unable to resolve relative test ID '{test_id}' to absolute ID. "
                      f"No test '{test_id.id}' found in series '{test_id.series}'.")
