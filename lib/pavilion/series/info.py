"""Object for summarizing series quickly."""
import datetime as dt
import json
from pathlib import Path
from typing import Union, List

from pavilion import config
from pavilion import dir_db
from pavilion import status_file
from pavilion import utils
from pavilion.errors import TestRunError, TestSeriesError
from pavilion.test_run import TestRun, TestAttributes
from . import common


class SeriesInfoBase:
    """Shared base class for series info and test set info."""

    def __init__(self, pav_cfg: config.PavConfig, path: Path):

        self._pav_cfg = pav_cfg

        self._config = None

        self.path = path

        self._complete = None

        self._tests = self._find_tests()
        self._test_statuses = None

        self._test_info = {}
        self._status: status_file.SeriesStatusInfo = None
        self._status_file: status_file.SeriesStatusFile = None

    @classmethod
    def list_attrs(cls):
        """Return a list of available attributes."""

        attrs = set([
            key for key, val in cls.__dict__.items()
            if isinstance(val, property)
        ])

        for par_class in cls.__bases__:
            if hasattr(par_class, 'list_attrs'):
                attrs.update(par_class.list_attrs())

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


        if attr in cls.__dict__:
            attr_prop = cls.__dict__[attr]
        else:
            for par_class in cls.__bases__:
                if attr in par_class.__dict__:
                    attr_prop = par_class.__dict__[attr]

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
    def user(self):
        """The user who created the suite."""
        try:
            return utils.owner(self.path)
        except KeyError:
            return None

    @property
    def created(self) -> float:
        """When the test series was created."""

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
    def errors(self) -> int:
        """Number of errors encountered while running the suite."""

        status_obj = self._get_status_file()

        errors = 0
        for status in status_obj.history():
            if status.state in (status_file.SERIES_STATES.ERROR,
                                status_file.SERIES_STATES.BUILD_ERROR,
                                status_file.SERIES_STATES.CREATION_ERROR,
                                status_file.SERIES_STATES.KICKOFF_ERROR):
                errors += 1

        for test_path in self._tests:
            test_info = self.test_info(test_path)
            if test_info is None:
                continue

            if test_info.result == TestRun.ERROR:
                errors += 1

        return errors

    def _get_test_statuses(self) -> List[str]:
        """Return a dict of the current status for each test."""

        if self._test_statuses is None:
            self._test_statuses = []
            for test_path in self._tests:

                status_fn = test_path/common.STATUS_FN
                status_obj = status_file.TestStatusFile(status_fn)

                self._test_statuses.append(status_obj.current().state)

        return self._test_statuses

    @property
    def running(self) -> int:
        """The number of currently running tests."""

        statuses = self._get_test_statuses()

        total = 0
        for status in statuses:
            if status == 'RUNNING':
                total += 1

        return total

    @property
    def scheduled(self) -> int:
        """The number of currently scheduled tests."""

        statuses = self._get_test_statuses()

        total = 0
        for status in statuses:
            if status == 'SCHEDULED':
                total += 1

        return total

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
            attr = getattr(self, item, None)
            return not callable(attr) and attr is not None

        return False

    def get(self, item, default=None):
        """Provided dictionary like get access."""

        if item in self:
            return self[item]
        else:
            return default


class SeriesInfo(SeriesInfoBase):
    """This class is a stop-gap. It's not meant to provide the same
    functionality as test_run.TestAttributes, but a lazily evaluated set
    of properties for a given series path. It should be replaced with
    something like TestAttributes in the future."""

    def __init__(self, pav_cfg: config.PavConfig, path: Path, check_tests=False):
        """
        :param check_tests: Do a full scheduler check on tests that aren't marked as complete
            when getting series completion status.
        """

        self._check_tests = check_tests

    def _find_tests(self):
        """Find all the tests for this series."""
        test_dict = common.LazyTestRunDict(self._pav_cfg, self.path)
        return list(test_dict.iter_paths())

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

    def _get_status_file(self) -> status_file.SeriesStatusFile:
        """Get the series status file object."""

        if self._status_file is None:
            status_fn = self.path/common.STATUS_FN
            if status_fn.exists():
                self._status_file = status_file.SeriesStatusFile(status_fn)

        return self._status_file

    def _get_status(self) -> status_file.SeriesStatusInfo:
        """Get the latest test state from the series status file."""

        if self._status is None:
            status_file = self._get_status_file()
            self._status = status_file.current()
        return self._status

    @property
    def sys_name(self) -> Union[str, None]:
        """The sys_name the series ran on."""

        if not self._tests:
            return None

        test_info = self.test_info(self._tests[0])
        if test_info is None:
            return None

        return test_info.sys_name

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

class TestSetInfo(SeriesInfoBase):
    """Information about a test set in a test series."""

    def __init__(self, pav_cfg: config.PavConfig, series_path: Path,
                 test_set_name: str):

        self.test_set_name = test_set_name
        self.test_set_path = series_path/'test_sets'/test_set_name

        if test_set_name and test_set_name[0].isdigit() and '.' in test_set_name:
            self._repeat, self._name = test_set_name.split('.', maxsplit=1)
        else:
            self._repeat = 0
            self._name = test_set_name



        super().__init__(pav_cfg, series_path)

    def _find_tests(self) -> List[Path]:
        """Find all the tests under the given test set."""

        if not (self.path/'test_sets').exists():
            raise TestSeriesError("Legacy test series does not have saved sets.")

        set_path = self.path/'test_sets'/self.test_set_name
        if not set_path.exists():
            avail_sets = [path.name for path in (self.series_path/'test_sets').iterdir()]
            raise TestSeriesError("Test Set '{}' does not exist for this series.\n"
                                  "Available sets are:\n  {}"
                                  .format(test_set_name, '  \n'.join(avail_sets)))

        set_paths = []
        for path in dir_db.select(self._pav_cfg, set_path, use_index=False).paths:
            if not path.is_symlink():
                continue
            try:
                set_paths.append(path)
            except ValueError:
                continue

        return set_paths

    @property
    def complete(self):
        complete_ts = common.get_test_set_complete(
            self._pav_cfg,
            self.test_set_path,
            check_tests=True)
        return complete_ts is not None

    @property
    def name(self):
        """The name of this test set."""
        return self._name

    @property
    def repeat(self):
        """The repeat iteration of this test set."""
        return self._repeat

    @property
    def created(self) -> float:
        """When the test set was created."""

        return self.test_set_path.stat().st_mtime



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
