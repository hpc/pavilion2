"""Object for summarizing series quickly."""

import datetime as dt
from pathlib import Path
import logging
import json

from pavilion import dir_db
from pavilion.test_run import TestRun, TestAttributes
from pavilion import system_variables
from pavilion import utils

logger = logging.getLogger()


class TestSeriesError(RuntimeError):
    """An error in managing a series of tests."""


class SeriesInfo:
    """This class is a stop-gap. It's not meant to provide the same
    functionality as test_run.TestAttributes, but a lazily evaluated set
    of properties for a given series path. It should be replaced with
    something like TestAttributes in the future."""

    def __init__(self, path: Path):

        self.path = path

        self._complete = None
        self._tests = [tpath for tpath in dir_db.select(self.path)[0]]

    @classmethod
    def list_attrs(cls):
        """Return a list of available attributes."""

        return [
            key for key, val in cls.__dict__.items()
            if isinstance(val, property)
        ]

    def attr_dict(self):
        """Return all values as a dict."""

        return {key: getattr(self, key) for key in self.list_attrs()}

    @classmethod
    def attr_doc(cls, attr):
        """Return the doc string for the given attributes."""

        if attr not in cls.list_attrs():
            raise KeyError("No such series attribute '{}'".format(attr))

        attr_prop = cls.__dict__[attr]
        return attr_prop.__doc__

    @property
    def sid(self):
        """The sid of this series."""

        return path_to_sid(self.path)

    @property
    def id(self):  # pylint: disable=invalid-name
        """The id of this series."""
        return int(self.path.name)

    @property
    def complete(self):
        """True if all tests are complete."""
        if self._complete is None:
            self._complete = all([(test_path / TestRun.COMPLETE_FN).exists()
                                  for test_path in self._tests])
        return self._complete

    @property
    def user(self):
        """The user who created the suite."""
        try:
            return self.path.owner()
        except KeyError:
            return None

    @property
    def created(self) -> dt.datetime:
        """When the test was created."""

        return dt.datetime.fromtimestamp(self.path.stat().st_mtime)

    @property
    def num_tests(self):
        """The number of tests belonging to this series."""
        return len(self._tests)

    @property
    def sys_name(self):
        """The sys_name the series ran on."""

        if not self._tests:
            return None

        return TestAttributes(self._tests[0]).sys_name


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


def load_user_series_id(pav_cfg):
    """Load the last series id used by the current user."""

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


def list_series_tests(pav_cfg, sid: str):
    """Return a list of paths to test run directories for the given series
id.
:raises TestSeriesError: If the series doesn't exist."""

    series_path = path_from_id(pav_cfg, sid)

    if not series_path.exists():
        raise TestSeriesError(
            "No such test series '{}'. Looked in {}."
            .format(sid, series_path))

    return dir_db.select(series_path)[0]


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
