"""Series are a collection of test runs."""

import logging
import os

from pavilion import utils
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


class TestSeriesError(RuntimeError):
    """An error in managing a series of tests."""


def test_obj_from_id(pav_cfg, test_ids):
    """Return the test object(s) associated with the id(s) provided.

:param dict pav_cfg: Base pavilion configuration.
:param list/str test_ids: One or more test IDs."
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

        if not tests:
            raise TestSeriesError("You cannot create a series of zero tests.")

        series_path = self.pav_cfg.working_dir/'series'

        # We're creating this series from scratch.
        if _id is None:
            # Get the series id and path.
            try:
                self._id, self.path = TestRun.create_id_dir(series_path)
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}': {}"
                    .format(series_path, err))

            # Create a soft link to the test directory of each test in the
            # series.
            for test in tests:
                link_path = utils.make_id_path(self.path, test.id)

                try:
                    link_path.symlink_to(test.path)
                except OSError as err:
                    raise TestSeriesError(
                        "Could not link test '{}' in series at '{}': {}"
                        .format(test.path, link_path, err))

            self._save_series_id()

        else:
            self._id = _id
            self.path = utils.make_id_path(series_path, self._id)

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self._id))

    @property
    def id(self):  # pylint: disable=invalid-name
        """Return the series id as a string, with an 's' in the front to
differentiate it from test ids."""

        return 's{}'.format(self._id)

    @classmethod
    def from_id(cls, pav_cfg, id_):
        """Load a series object from the given id, along with all of its
associated tests."""

        series_path = pav_cfg.working_dir/'series'
        series_path = utils.make_id_path(series_path, id_)

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

                tests.append(TestRun.load(pav_cfg, test_id=test_id))
            else:
                logger.info("Polluted series directory in series '%s'",
                            series_path)
                raise ValueError(link_path)

        return cls(pav_cfg, tests, _id=id_)

    def _save_series_id(self):
        """Save the series id to the user's .pavilion directory."""

        # Save the last series we created to the .pavilion directory
        # in the user's home dir. Pavilion commands can use this so the
        # user doesn't actually have to know the series_id of tests.

        last_series_fn = self.pav_cfg.working_dir/'users'
        last_series_fn /= '{}.series'.format(utils.get_login())
        try:
            with last_series_fn.open('w') as last_series_file:
                last_series_file.write(self.id)
        except (IOError, OSError):
            # It's ok if we can't write this file.
            self._logger.warning("Could not save series id to '%s'",
                                 last_series_fn)

    @classmethod
    def load_user_series_id(cls, pav_cfg):
        """Load the last series id used by the current user."""
        logger = logging.getLogger(cls.LOGGER_FMT.format('<unknown>'))

        last_series_fn = pav_cfg.working_dir/'users'
        last_series_fn /= '{}.series'.format(utils.get_login())

        if not last_series_fn.exists():
            return None
        try:
            with last_series_fn.open() as last_series_file:
                return last_series_file.read().strip()
        except (IOError, OSError) as err:
            logger.warning("Failed to read series id file '%s': %s",
                           last_series_fn, err)
            return None

    @property
    def timestamp(self):
        """Return the unix timestamp for this series, based on the last
modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return self.path.stat().st_mtime
