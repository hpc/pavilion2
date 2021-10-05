"""Object for summarizing series quickly."""
import logging
from pathlib import Path

from pavilion import dir_db
from pavilion import utils
from pavilion.test_run import TestRun, TestAttributes
from .errors import TestSeriesError

logger = logging.getLogger()


class SeriesInfo:
    """This class is a stop-gap. It's not meant to provide the same
    functionality as test_run.TestAttributes, but a lazily evaluated set
    of properties for a given series path. It should be replaced with
    something like TestAttributes in the future."""

    def __init__(self, pav_cfg, path: Path):

        self.path = path

        self._complete = None
        self._tests = [tpath for tpath in dir_db.select(pav_cfg, self.path).paths]

    @classmethod
    def list_attrs(cls):
        """Return a list of available attributes."""

        attrs = [
            key for key, val in cls.__dict__.items()
            if isinstance(val, property)
        ]

        attrs.append('path')

        return attrs

    def attr_dict(self):
        """Return all values as a dict."""

        attr_dict = {key: getattr(self, key) for key in self.list_attrs()}
        attr_dict['path'] = self.path.as_posix()

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
            return utils.owner(self.path)
        except KeyError:
            return None

    @property
    def created(self) -> float:
        """When the test was created."""

        return self.path.stat().st_mtime

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


def mk_series_info_transform(pav_cfg):
    """Create and return a series info transform function."""

    def series_info_transform(path):
        """Transform a path into a series info dict."""

        return SeriesInfo(pav_cfg, path).attr_dict()

    return series_info_transform


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
