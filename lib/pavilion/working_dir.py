import grp
import stat
import os

from pathlib import PosixPath, Path
from typing import Optional, Tuple, List

from pavilion import dir_db
from pavilion.micro import set_default
from pavilion.errors import PavConfigError
from pavilion.counter import SeriesIDCounter
from pavilion.test_ids import SeriesID, TestID
from pavilion.errors import TestSeriesError


class WorkingDirectory(PosixPath):
    BUILDS_DIR_NAME = "builds"
    GROUPS_DIR_NAME = "groups"
    JOBS_DIR_NAME = "jobs"
    SERIES_DIR_NAME = "series"
    TEST_RUNS_DIR_NAME = "test_runs"
    TEST_SETS_DIR_NAME = "test_sets"
    USERS_DIR_NAME = "users"

    DEFAULT_PERMISSIONS = 0o770

    def __new__(cls, path: str, group: Optional[str] = None):
        self = super().__new__(cls, path)

        self._group = group

        self.builds_dir = self / self.BUILDS_DIR_NAME
        self.groups_dir = self/ self.GROUPS_DIR_NAME
        self.jobs_dir = self / self.JOBS_DIR_NAME
        self.series_dir = self / self.SERIES_DIR_NAME
        self.test_runs_dir = self / self.TEST_RUNS_DIR_NAME
        self.users_dir = self / self.USERS_DIR_NAME

        self._test_counters = {}

        return self

    def setup(self, permissions: Optional[int] = None):
        permissions = set_default(permissions, self.DEFAULT_PERMISSIONS)

        if not self.exists():
            self.mkdir()

            if self._group is not None:
                self.set_group(self._group)
                self.set_permissions(self.DEFAULT_PERMISSIONS)
        else:
            if self._group is not None and self.group != self._group:
                raise PavConfigError(f"Working dir should have group '{self._group}', but has "
                        f"group '{self.group}'. This usually means two config directories specify "
                        "different groups but point to the same working directory. See "
                        "`pav config list`.")

        self.make_subdirs()

    def make_subdirs(self) -> None:
        for subdir in (self.builds_dir, self.groups_dir, self.jobs_dir, self.series_dir,
                       self.test_runs_dir, self.users_dir):
            try:
                subdir.mkdir(exist_ok=True)
            except OSError:
                raise PavConfigError(f"Could not create directory '{(self / subdir)}'", err)

        self._series_counter = SeriesIDCounter(self.series_dir)

    def set_group(self, group) -> None:
        try:
            group_struct = grp.getgrnam(group)
        except KeyError:
            raise PavConfigError(f"Group specified ({group}) for working_dir "
                                    f"'{self}' does not exist.")
        try:
            os.chown(self, -1, group_struct.gr_gid)
        except OSError as err:
            raise PavConfigError(f"Could not set group working dir '{self}'", err)

    def set_permissions(self, permissions: int, setgid: bool = True) -> None:
        if setgid:
            new_permissions = stat.S_ISGID
        else:
            new_permissions = 0

        try:
            self.chmod(new_permissions | permissions)
        except OSError as err:
            raise PavConfigError(f"Could not set permissions on working dir '{self}'", err)

    def new_build(self, name: str):
        ...

    def new_series(self, mkdir: bool = False) -> Tuple[SeriesID, Path]:
        next_id = next(self._series_counter)
        path = self.series_dir / str(next_id.as_int())

        if mkdir:
            path.mkdir()

        return next_id, path

    def get_series_path(self, sid: SeriesID) -> Path:
        """Given a series ID, return the path to that series' directory."""

        return self.series_dir / str(sid.as_int())

    def list_series_tests(self, sid: SeriesID, max_threads: int = 1) -> List[Path]:
        """Return a list of paths to test run directories for the given series ID."""

        series_path = self.get_series_path(sid)

        if not series_path.exists():
            raise TestSeriesError(
                "No such test series '{}'. Looked in {}."
                .format(sid, series_path))

        test_runs_path = series_path / self.TEST_RUNS_DIR_NAME

        if test_runs_path.exists():
            return dir_db.select(test_runs_path, max_threads=max_threads).paths

        return []

    def get_last_series_id(self, user: str, sys_name: str) -> Optional[SeriesID]:
        """Given a username and system name, return the most recent series ID run by that user on
        that system."""

        user_fname = self.users_dir / f"{user}.json"

        if not user_fname.exists():
            return None

        try:
            with user_fname.open() as fin:
                user_info = json.load(fin)

            return SeriesID(user_info[sys_name].strip())
        except (IOError, OSError, KeyError) as err:
            raise TestSeriesError(f"Failed to read series ID file '{user_fname}'.")

    def new_test_set(self, sid: SeriesID, name: str, mkdir: bool = False) -> Path:
        path = self.series_dir / str(sid.as_int()) / self.TEST_SETS_DIR_NAME / name

        if mkdir:
            path.mkdir(parents=True, exist_ok=True)

        return path

    def new_test(self, sid: SeriesID, test_set_name: Optional[str], mkdir: bool = False) -> Tuple[TestID, Path]:
        if sid in self._test_counters:
            counter = self._test_counters.get(sid)
        else:
            counter = TestIDCounter(sid, self.test_runs_dir)
            self._test_counters[sid] = counter

        next_id = next(counter)
        test_path = self.test_runs_dir / str(next_id)
        series_path = self.series_dir / str(sid.as_int())

        if mkdir:
            path.mkdir()
            (series_path / self.TEST_RUNS_DIR_NAME).mkdir(exist_ok=True, parents=True)

            (test_path / self.SERIES_DIR_NAME).symlink_to(series_path)
            (series_path / self.TEST_RUNS_DIR_NAME / str(next_id)).symlink_to(test_path)

            if test_set_name is not None:
                test_set_path = self.new_test_set(sid, test_set_name, mkdir=True)
                (test_set_path / str(next_id)).symlink_to(test_path)

        return next_id, test_path

    def get_test_path(self, test_id: TestID) -> Path:
        """Given a test ID, return the path to that test's test run directory."""

        if test_id.is_relative():
            # Use the series directory's symlink to the test, so we don't have to worry about which
            # config directory it's in
            series_path = self.get_series_path(test_id.series)

            path = (series_path / self.TEST_RUNS_DIR_NAME / str(test_id)).resolve()
        else:
            path = self.test_runs_dir / str(test_id)

        return path

    def new_group(self, name: str, mkdir: bool = False) -> Path:
        path = self.groups_dir / name

        if mkdir:
            self.path.mkdir(exist_ok=True)

        return path

