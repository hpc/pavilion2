"""Object for summarizing series quickly."""
import datetime as dt
import json
from pathlib import Path
from typing import Union

from pavilion import config
from pavilion import dir_db
from pavilion import status_file
from pavilion import utils
from pavilion.exceptions import TestRunError
from pavilion.test_run import TestRun, TestAttributes
from . import common
from .errors import TestSeriesError


class SeriesInfo:
    """This class is a stop-gap. It's not meant to provide the same
    functionality as test_run.TestAttributes, but a lazily evaluated set
    of properties for a given series path. It should be replaced with
    something like TestAttributes in the future."""

    def __init__(self, pav_cfg: config.PavConfig, path: Path):

        self._pav_cfg = pav_cfg

        self._config = None

        self.path = path

        self._complete = None
        self._tests = [tpath for tpath in dir_db.select(pav_cfg, self.path).paths]
        # Test info objects for

        self._test_info = {}
        self._status: Union[None, status_file.SeriesStatusInfo] = None

    @classmethod
    def list_attrs(cls):
        """Return a list of available attributes."""

        attrs = [
            key for key, val in cls.__dict__.items()
            if isinstance(val, property)
        ]

        return attrs

    def attr_dict(self):
        """Return all values as a dict."""

        attr_dict = {key: getattr(self, key) for key in self.list_attrs()}
        attr_dict['path'] = self.path.as_posix()
        return attr_dict

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
    def name(self):
        """Return the series name."""

        try:
            with open(self.path/common.CONFIG_FN) as config_file:
                self._config = json.load(config_file)
        except json.JSONDecodeError:
            return '<unknown>'

        return self._config.get('name', '<unknown>')

    @property
    def complete(self):
        """True if all tests are complete."""

        return common.get_complete(self._pav_cfg, self.path, check_tests=True) is not None

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
    def finished(self) -> Union[float, None]:
        """When the series completion file was created."""

        complete_fn = self.path/common.COMPLETE_FN
        if complete_fn.exists():
            return complete_fn.stat().st_mtime
        else:
            return None

    @property
    def num_tests(self) -> int:
        """The number of tests belonging to this series."""
        return len(self._tests)

    @property
    def passed(self) -> int:
        """Number of tests that have passed."""

        passed = 0
        for test_path in self._tests:
            test_info = self.test_info(test_path)
            if test_info is None:
                continue

            if test_info.result == TestRun.PASS:
                passed += 1

        return passed

    @property
    def failed(self) -> int:
        """Number of tests that have failed."""

        failed = 0
        for test_path in self._tests:
            test_info = self.test_info(test_path)
            if test_info is None:
                continue

            if test_info.result == TestRun.FAIL:
                failed += 1

        return failed

    @property
    def status(self) -> Union[str, None]:
        """The last status message from the series status file."""

        status = self._get_status()
        if status is None:
            return None
        return self._status.state

    @property
    def status_note(self) -> Union[str, None]:
        """Return the series status note."""

        status = self._get_status()
        if status is None:
            return None
        return self._status.note

    @property
    def status_when(self) -> Union[dt.datetime, None]:
        """Return the most recent status update time."""

        status = self._get_status()
        if status is None:
            return None
        return self._status.when

    def _get_status(self) -> status_file.SeriesStatusInfo:
        """Get the latest status and note from the series status file."""

        if self._status is None:
            status_fn = self.path/common.STATUS_FN
            if status_fn.exists():
                series_status = status_file.SeriesStatusFile(status_fn)
                sstatus = series_status.current()
                self._status = sstatus

        return self._status

    @property
    def errors(self) -> int:
        """Number of tests that are complete but with no result, or
        with an ERROR result."""

        errors = 0
        for test_path in self._tests:
            test_info = self.test_info(test_path)
            if test_info is None:
                continue

            if (test_info.complete and
                    test_info.result not in (TestRun.PASS, TestRun.FAIL)):
                errors += 1

        return errors

    @property
    def sys_name(self) -> Union[str, None]:
        """The sys_name the series ran on."""

        if not self._tests:
            return None

        test_info = self.test_info(self._tests[0])
        if test_info is None:
            return None

        return test_info.sys_name

    def test_info(self, test_path) -> Union[TestAttributes, None]:
        """Return the test info object for the given test path.
        If the test doesn't exist, return None."""

        if test_path in self._test_info:
            return self._test_info[test_path]

        try:
            test_info = TestAttributes(test_path)
        except TestRunError:
            test_info = None

        self._test_info[test_path] = test_info
        return test_info

    @classmethod
    def load(cls, pav_cfg: config.PavConfig, sid: str):
        """Find and load a series info object from a series id."""

        try:
            id_ = int(sid[1:])
        except ValueError:
            raise TestSeriesError(
                "Invalid series id '{}'. Series id should "
                "look like 's1234'.".format(sid))

        series_path = pav_cfg.working_dir/'series'/str(id_)
        if not series_path.exists():
            raise TestSeriesError("Could not find series '{}'".format(sid))
        return cls(pav_cfg, series_path)

    def __getitem__(self, item):
        """Dictionary like access."""

        if not isinstance(item, str) or item.startswith('_'):
            raise KeyError("Invalid key in SeriesInfo (bad key): {}".format(item))

        if hasattr(self, item):
            attr = getattr(self, item)
            if callable(attr):
                raise KeyError("Invalid key in SeriesInfo (callable): {}".format(item))
            return attr

        else:
            raise KeyError("Unknown key in SeriesInfo: {}".format(item))

    def __contains__(self, item) -> bool:
        """Provide dictionary like 'contains' checks."""

        if isinstance(item, str) and not item.startswith('_'):
            attr = getattr(self, item)
            return not callable(attr)

        return False

    def get(self, item, default=None):
        """Provided dictionary like get access."""

        if item in self:
            return self[item]
        else:
            return default


def mk_series_info_transform(pav_cfg):
    """Create and return a series info transform function."""

    def series_info_transform(path):
        """Transform a path into a series info dict."""

        return SeriesInfo(pav_cfg, path)

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
