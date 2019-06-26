from pavilion.pav_test import PavTest
from pavilion import utils
from pathlib import Path
import logging
import os


class TestSeriesError(RuntimeError):
    """An error in managing a series of tests."""
    pass


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
                self._id, self.path = utils.create_id_dir(series_path)
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
    def id(self):
        """Return the series id as a string, with an 's' in the front to
        differentiate it from test ids."""

        return 's{}'.format(self._id)

    @classmethod
    def from_id(cls, pav_cfg, id_):

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
                        "Bad test id in series from dir '{}'"
                        .format(link_path))
                    continue

                tests.append(PavTest.load(pav_cfg, test_id=test_id))
            else:
                logger.info(
                    "Polluted series directory in series '{}'"
                    .format(series_path))
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
            self._logger.warning("Could not save series id to '{}'"
                                 .format(last_series_fn))

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
            logger.warning("Failed to read series id file '{}': {}"
                           .format(last_series_fn, err))
            return None

    @property
    def ts(self):
        """Return the unix timestamp for this series, based on the last
        modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return self.path.stat().st_mtime
