"""Series are a collection of test runs."""

import datetime as dt
import json
import logging
import errno
import time
from pathlib import Path

from pavilion import dir_db
from pavilion import system_variables
from pavilion import utils
from pavilion import schedulers
from pavilion import output
from pavilion.permissions import PermissionsManager
from pavilion.output import fprint
from pavilion.lockfile import LockFile
from pavilion.status_file import STATES
from pavilion.test_run import (
    TestRun, TestRunError, TestRunNotFoundError, TestAttributes)


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
                self._id, self.path = dir_db.create_id_dir(
                    series_path,
                    pav_cfg['shared_group'],
                    pav_cfg['umask'])
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}': {}"
                    .format(series_path, err))

            perm_man = PermissionsManager(None, pav_cfg['shared_group'],
                                          pav_cfg['umask'])
            # Create a soft link to the test directory of each test in the
            # series.
            for test in tests:
                link_path = dir_db.make_id_path(self.path, test.id)

                try:
                    link_path.symlink_to(test.path)
                    perm_man.set_perms(link_path)
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

    def run_tests(self, pav_cfg, wait, report_status, outfile, errfile):
        """
        :param pav_cfg:
        :param int wait: Wait this long for a test to start before exiting.
        :param bool report_status: Do a 'pav status' after tests have started.
            on nodes, and kick them off in build only mode.
        :param Path outfile: Direct standard output to here.
        :param Path errfile: Direct standard error to here.
        :return:
        """

        SLEEP_INTERVAL = 1

        all_tests = list(self.tests.values())

        for test in self.tests.values():
            sched_name = test.scheduler
            sched = schedulers.get_plugin(sched_name)

            if not sched.available():
                fprint("1 test started with the {} scheduler, but"
                       "that scheduler isn't available on this system."
                       .format(sched_name),
                       file=errfile, color=output.RED)
                return errno.EINVAL

        for test in self.tests.values():

            # don't run this test if it was meant to be skipped
            if test.skipped:
                continue

            # tests that are build-only or build-local should already be completed, therefore don't run these
            if test.complete:
                continue

            sched = schedulers.get_plugin(test.scheduler)
            try:
                sched.schedule_tests(pav_cfg, [test])
            except schedulers.SchedulerPluginError as err:
                fprint('Error scheduling test: ', file=errfile,
                       color=output.RED)
                fprint(err, bullet='  ', file=errfile)
                fprint('Cancelling already kicked off tests.',
                       file=errfile)
                sched.cancel_job(test)
                return errno.EINVAL

        # Tests should all be scheduled now, and have the SCHEDULED state
        # (at some point, at least). Wait until something isn't scheduled
        # anymore (either running or dead), or our timeout expires.
        wait_result = None
        if wait is not None:
            end_time = time.time() + wait
            while time.time() < end_time and wait_result is None:
                last_time = time.time()
                for test in self.tests.values():
                    sched = schedulers.get_plugin(test.scheduler)
                    status = test.status.current()
                    if status == STATES.SCHEDULED:
                        status = sched.job_status(pav_cfg, test)

                    if status != STATES.SCHEDULED:
                        # The test has moved past the scheduled state
                        wait_result = None
                        break

                if wait_result is None:
                    # Sleep at most SLEEP INTERVAL seconds, minus the time
                    # we spent checking our jobs.
                    time.sleep(SLEEP_INTERVAL - (time.time() - last_time))

        fprint("{} test{} started as test series {}."
               .format(len(all_tests),
                       's' if len(all_tests) > 1 else '',
                       self.sid),
               file=outfile,
               color=output.GREEN)

        if report_status:
            from pavilion.plugins.commands.status import print_from_tests
            return print_from_tests(
                pav_cfg=pav_cfg,
                tests=list(self.tests.values()),
                outfile=outfile)

        return 0

    @property
    def sid(self):  # pylint: disable=invalid-name
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
    def sid_to_id(cls, sid: str) -> int:
        """Convert a sid string to a numeric series id.

        :raises TestSeriesError: On an invalid sid.
        """

        if not sid.startswith('s'):
            raise TestSeriesError(
                "Invalid SID '{}'. Must start with 's'.".format(sid))

        try:
            return int(sid[1:])
        except ValueError:
            raise TestSeriesError(
                "Invalid SID '{}'. Must end in an integer.".format(sid))

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

        return dir_db.select(series_path)[0]

    @classmethod
    def from_id(cls, pav_cfg, sid: str):
        """Load a series object from the given id, along with all of its
    associated tests.

        :raises TestSeriesError: From invalid series id or path.
        """

        sid = cls.sid_to_id(sid)

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, sid)

        if not series_path.exists():
            raise TestSeriesError("No such series found: '{}' at '{}'"
                                  .format(sid, series_path))

        logger = logging.getLogger(cls.LOGGER_FMT.format(sid))

        tests = []
        for path in dir_db.select(series_path)[0]:
            try:
                test_id = int(path.name)
            except ValueError:
                logger.info("Bad test id in series from dir '%s'", path)
                continue

            try:
                tests.append(TestRun.load(pav_cfg, test_id=test_id))
            except TestRunError as err:
                logger.info("Error loading test %s: %s",
                            test_id, err.args[0])

        return cls(pav_cfg, tests, _id=sid)

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
                    except json.decoder.JSONDecodeError:
                        # File was empty, therefore json couldn't be loaded.
                        pass
                with PermissionsManager(json_file, self.pav_cfg['shared_group'],
                                        self.pav_cfg['umask']), \
                        json_file.open('w') as json_series_file:
                    data[sys_name] = self.sid
                    json_series_file.write(json.dumps(data))

            except FileNotFoundError:
                # File hadn't been created yet.
                with PermissionsManager(json_file, self.pav_cfg['shared_group'],
                                        self.pav_cfg['umask']), \
                         json_file.open('w') as json_series_file:
                    data[sys_name] = self.sid
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

        return TestSeries.path_to_sid(self.path)

    @property
    def id(self):
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

