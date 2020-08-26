"""This module contains functions to generate filter functions for handing
to dir_db commands."""

import datetime as dt
import json
from pathlib import Path

from pavilion.test_run import TestRun


def make_test_run_filter(
    complete=False, failed=False, incomplete=False, newer_than=None,
    older_than=None, passed=False, show_skipped=False, sys_names=None,
    users=None):
    """
    :param complete:
    :param failed:
    :param incomplete:
    :param newer_than:
    :param older_than:
    :param passed:
    :param show_skipped:
    :param sys_names:
    :param users:
    :return:
    """

    #  select once so we only make one filter.
    def filter_tests(test_path: Path) -> bool:

        try:
            if complete and not (test_path / 'RUN_COMPLETE').exists():
                return False
            if incomplete and (test_path / 'RUN_COMPLETE').exists():
                return False

            if users is not None:
                try:
                    if test_path.owner() not in users:
                        return False
                except KeyError:
                    # The uid that owns this file does not exist on this system.
                    return False

            if sys_names is not None or older_than or newer_than:
                with open(test_path / 'variables') as var_file:
                    vars = json.load(var_file)

            if sys_names is not None:
                sys_name = vars.get('sys', {}).get('sys_name')
                if sys_name not in sys_names:
                    return False

            if passed or failed:
                with open(test_path) as file:
                    results = json.load(file)

            if passed and results.get('result') != TestRun.PASS:
                return False

            if failed and results.get('result') != TestRun.FAIL:
                return False

            stat = test_path.stat()
            test_time = dt.datetime.fromtimestamp(stat.st_mtime)

            if older_than is not None and test_time <= older_than:
                return False
            if newer_than is not None and test_time >= newer_than:
                return False

        except (FileNotFoundError, NotADirectoryError, OSError):
            return False

        return True

    return filter_tests
