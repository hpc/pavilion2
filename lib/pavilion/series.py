"""Series are a collection of test runs."""

import logging
import json
import os
from pathlib import Path

from pavilion import system_variables
from pavilion import utils
from pavilion.lockfile import LockFile
from pavilion import dir_db
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


class TestSeriesError(RuntimeError):
    """An error in managing a series of tests."""


def test_obj_from_id(pav_cfg, test_ids):
    """Return the test object(s) associated with the id(s) provided.

    :param dict pav_cfg: Base pavilion configuration.
    :param Union(list,str) test_ids: One or more test IDs."
    :return tuple(list(test_obj),list(failed_ids)): tuple containing a list of
        test objects and a list of test IDs for which no test could be found.
    """

    test_obj_list = []
    test_failed_list = []

    if not isinstance(test_ids, list):
        test_ids = [test_ids]

    for test_id in test_ids:
        try:
            test = TestRun.load(pav_cfg, test_id)
            test_obj_list.append(test)
        except (TestRunError, TestRunNotFoundError):
            test_failed_list.append(test_id)

    return test_obj_list, test_failed_list


class TestSeries:
    """Series are a collection of tests. Every time """

    LOGGER_FMT = 'series({})'

    def __init__(self, pav_cfg, tests, _id=None):
        """Initialize the series.

        :param pav_cfg: The pavilion configuration object.
        :param list tests: The list of test objects that belong to this series.
        :param int _id: The test id number. If this is given, it implies that
            we're regenerating this series from saved files.
        """

        self.pav_cfg = pav_cfg
        self.tests = {test.id: test for test in tests}

        series_path = self.pav_cfg.working_dir/'series'

        # We're creating this series from scratch.
        if _id is None:
            # Get the series id and path.
            try:
                self._id, self.path = dir_db.create_id_dir(series_path)
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}': {}"
                    .format(series_path, err))

            # Create a soft link to the test directory of each test in the
            # series.
            for test in tests:
                link_path = dir_db.make_id_path(self.path, test.id)

                try:
                    link_path.symlink_to(test.path)
                except OSError as err:
                    raise TestSeriesError(
                        "Could not link test '{}' in series at '{}': {}"
                        .format(test.path, link_path, err))

            # Update user.json to record last series run per sys_name
            self._save_series_id()

        else:
            self._id = _id
            self.path = dir_db.make_id_path(series_path, self._id)

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self._id))

    @property
    def id(self):  # pylint: disable=invalid-name
        """Return the series id as a string, with an 's' in the front to
differentiate it from test ids."""

        return 's{}'.format(self._id)

    @staticmethod
    def path_to_sid(series_path: Path):
        """Return the sid for a given series path.
        :raises TestSeriesError: For an invalid series path."""

        try:
            return 's{}'.format(int(series_path.name))
        except ValueError:
            raise TestSeriesError(
                "Series paths must have a numerical directory name, got '{}'"
                    .format(series_path.as_posix())
            )

    @classmethod
    def path_from_id(cls, pav_cfg, sid: str):
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

    @classmethod
    def list_series_tests(cls, pav_cfg, sid: str):
        """Return a list of paths to test run directories for the given series
        id.
        :raises TestSeriesError: If the series doesn't exist.
        """

        series_path = cls.path_from_id(pav_cfg, sid)

        if not series_path.exists():
            raise TestSeriesError(
                "No such test series '{}'. Looked in {}."
                    .format(sid, series_path))

        return dir_db.select(series_path)

    @classmethod
    def from_id(cls, pav_cfg, id_):
        """Load a series object from the given id, along with all of its
associated tests."""

        try:
            id_ = int(id_[1:])
        except TypeError as err:
            pass

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, id_)

        if not series_path.exists():
            raise TestSeriesError("No such series found: '{}' at '{}'"
                                  .format(id_, series_path))

        logger = logging.getLogger(cls.LOGGER_FMT.format(id_))

        tests = []
        for path in os.listdir(str(series_path)):
            link_path = series_path/path
            if link_path.is_symlink() and link_path.is_dir():
                try:
                    test_id = int(link_path.name)
                except ValueError:
                    logger.info(
                        "Bad test id in series from dir '%s'",
                        link_path)
                    continue

                try:
                    tests.append(TestRun.load(pav_cfg, test_id=test_id))
                except TestRunError as err:
                    logger.info(
                        "Error loading test %s: %s",
                        test_id, err
                    )

            else:
                logger.info("Polluted series directory in series '%s'",
                            series_path)
                raise ValueError(link_path)

        return cls(pav_cfg, tests, _id=id_)

    def _save_series_id(self):
        """Save the series id to json file that tracks last series ran by user
        on a per system basis."""

        sys_vars = system_variables.get_vars(True)
        sys_name = sys_vars['sys_name']

        json_file = self.pav_cfg.working_dir/'users'
        json_file /= '{}.json'.format(utils.get_login())

        lockfile_path = json_file.with_suffix('.lock')

        with LockFile(lockfile_path):
            data = {}
            try:
                with json_file.open('r') as json_series_file:
                    try:
                        data = json.load(json_series_file)
                    except json.decoder.JSONDecodeError as err:
                        # File was empty, therefore json couldn't be loaded.
                        pass
                with json_file.open('w') as json_series_file:
                    data[sys_name] = self.id
                    json_series_file.write(json.dumps(data))

            except FileNotFoundError as err:
                # File hadn't been created yet.
                with json_file.open('w') as json_series_file:
                    data[sys_name] = self.id
                    json_series_file.write(json.dumps(data))

    @classmethod
    def load_user_series_id(cls, pav_cfg):
        """Load the last series id used by the current user."""
        logger = logging.getLogger(cls.LOGGER_FMT.format('<unknown>'))

        last_series_fn = pav_cfg.working_dir/'users'
        last_series_fn /= '{}.json'.format(utils.get_login())

        sys_vars = system_variables.get_vars(True)
        sys_name = sys_vars['sys_name']

        if not last_series_fn.exists():
            return None
        try:
            with last_series_fn.open() as last_series_file:
                sys_name_series_dict = json.load(last_series_file)
                return sys_name_series_dict[sys_name].strip()
        except (IOError, OSError, KeyError) as err:
            logger.warning("Failed to read series id file '%s': %s",
                           last_series_fn, err)
            return None

    @property
    def timestamp(self):
        """Return the unix timestamp for this series, based on the last
modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return self.path.stat().st_mtime
