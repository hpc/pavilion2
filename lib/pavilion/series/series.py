"""Series are built around a config that specifies a 'series' of tests to run. It
also tracks the tests that have run under it."""
import io
import json
import math
import os
import re
import signal
import sys
import subprocess
import time
from collections import defaultdict, OrderedDict
from pathlib import Path
from typing import List, Dict, Set, Union, TextIO, Iterator

import pavilion
from pavilion import cancel_utils
from pavilion import config
from pavilion import dir_db
from pavilion import output
from pavilion import sys_vars
from pavilion import utils
from pavilion.enums import Verbose
from pavilion.lockfile import LockFile
from pavilion.output import fprint
from pavilion.series_config import SeriesConfigLoader
from pavilion.status_file import SeriesStatusFile, SERIES_STATES
from pavilion.test_run import TestRun
from pavilion.types import ID_Pair
from yaml_config import YAMLError, RequiredError
from .info import SeriesInfo
from .test_set import TestSet
from ..errors import TestSetError, TestSeriesError, TestSeriesWarning
from . import common


class TestSeries:
    """Series are a well defined collection of tests, potentially with
    relationships, skip conditions, and other features by test set. The test runs
    in a series include all tests that have been created for that series, but not
    necessarily all tests that will be created. These are organized into 'TestSets'
    while being manipulated. A series is complete when all test sets have run under
    the series as specified by its config, or when an error occurs. Series are
    identified by a 'sid', which takes the form 's<id_num>'."""

    DEPENDENCY_FN = 'dependency'
    OUT_FN = 'series.out'
    PGID_FN = 'series.pgid'
    NAME_RE = re.compile('[a-z][a-z0-9_-]+$')

    def __init__(self, pav_cfg: config.PavConfig, series_cfg, _id=None,
                 verbosity: Verbose = Verbose.HIGH, outfile: TextIO = None):
        """Initialize the series. Test sets may be added via 'add_tests()'.

        :param pav_cfg: The pavilion configuration object.
        :param series_cfg: Series config, if generated from a series file.
        :param _id: The test id number. If this is given, it implies that
            we're regenerating this series from saved files.
        """

        self.pav_cfg: config.PavConfig = pav_cfg

        self.config = series_cfg or SeriesConfigLoader().load_empty()

        self.outfile = io.StringIO() if outfile is None else outfile
        self.verbosity = verbosity

        name = self.config.get('name') or 'unnamed'
        if not self.NAME_RE.match(name):
            raise TestSeriesError(
                "Invalid Series name: {}. Series names must start with a letter, and can "
                "contain numbers, dashes and underscores.".format(series_cfg['name']))
        self.name = name

        series_path = self.pav_cfg.working_dir/'series'

        self.simultaneous = self.config.get('simultaneous')
        if self.simultaneous in (0, None):
            self.simultaneous = 2**32
        self.batch_size = max(self.simultaneous//2, 1)

        self.repeat = self.config['repeat']

        self._pgid = None

        self.test_sets = OrderedDict()

        self.ignore_errors = self.config['ignore_errors']

        # We're creating this series from scratch.
        if _id is None:
            # Get the series id and path.
            try:
                self._id, self.path = dir_db.create_id_dir(series_path)
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}'"
                    .format(series_path), err)

            # save series config
            self.save_config()

            # Update user.json to record last series run per sys_name
            self._save_series_id()
            self.status = SeriesStatusFile(self.path/common.STATUS_FN)
            self.status.set(SERIES_STATES.CREATED, "Created series.")

        # We're not creating this from scratch (an object was made ahead of
        # time).
        else:
            self._id = _id
            self.path = dir_db.make_id_path(series_path, self._id)
            self.status = SeriesStatusFile(self.path/common.STATUS_FN)

        self.tests = common.LazyTestRunDict(pav_cfg, self.path)

    def run_background(self):
        """Run pav _series in background using subprocess module."""

        self.status.set(SERIES_STATES.RUN, "Managing series in the background.")

        # This is normally, but not necessarily, in the users PATH
        pav_exe = Path(pavilion.__file__).resolve().parents[2]/'bin'/'pav'

        # Similarly, we need to tell Pavilion where to find it's config.
        env = os.environ.copy()
        pav_cfg = self.pav_cfg.pav_cfg_file
        pav_cfg = pav_cfg.parent.resolve()/pav_cfg.name
        env['PAV_CONFIG_FILE'] = pav_cfg.resolve()

        # start subprocess
        temp_args = [pav_exe, '_series', self.sid]
        try:
            series_out_path = self.path/self.OUT_FN
            with series_out_path.open('w') as series_out:
                series_proc = subprocess.Popen(temp_args,
                                               # Detach from this process. This will prevent
                                               # killing the child from bubbling up to the
                                               # parent, particularly in unit tests.
                                               start_new_session=True,
                                               env=env,
                                               stdout=series_out,
                                               stderr=series_out)

        except OSError as err:
            raise TestSeriesError("Could not start series '{}' in the background."
                                  .format(self.sid), err)

        # write pgid to a file (atomically)
        series_pgid = os.getpgid(series_proc.pid)
        series_pgid_path = self.path/self.PGID_FN
        try:
            series_pgid_tmp = series_pgid_path.with_suffix('.tmp')
            with series_pgid_tmp.open('w') as series_id_file:
                series_id_file.write(str(series_pgid))

            series_pgid_tmp.rename(series_pgid_path)
        except OSError:
            raise TestSeriesWarning("Could not write series PGID to a file.")

    def get_currently_running(self):
        """Returns list of tests that have states of either SCHEDULED or
        RUNNING. """

        cur_run = []
        for test_id, test_obj in self.tests.items():
            temp_state = test_obj.status.current().state
            if temp_state in ['SCHEDULED', 'RUNNING']:
                cur_run.append(test_obj)
        return cur_run

    def save_config(self) -> None:
        """Saves series config to a file."""

        series_config_path = self.path/common.CONFIG_FN
        try:
            series_config_tmp = series_config_path.with_suffix('.tmp')
            with series_config_tmp.open('w') as config_file:
                config_file.write(json.dumps(self.config))

            series_config_path.with_suffix('.tmp').rename(series_config_path)
        except OSError:
            raise TestSeriesError(
                "Could not write series config to file. Cancelling.")

    def test_set_dirs(self) -> Iterator[Path]:
        """Return an iterator over the test set directories for this series."""

        if (self.path/'test_sets').exists():
            for dir in (self.path/'test_sets').iterdir():
                if dir.is_dir():
                    yield dir

    @property
    def sid(self):  # pylint: disable=invalid-name
        """Return the series id as a string, with an 's' in the front to
differentiate it from test ids."""

        return 's{}'.format(self._id)

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
    def load(cls, pav_cfg, sid: Union[str, int], outfile=None):
        """Load a series object from the given id, along with all of its
    associated tests.

    :raises TestSeriesError: From invalid series id or path."""

        if isinstance(sid, str):
            series_id = cls.sid_to_id(sid)
        else:
            series_id = sid

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, series_id)

        if not series_path.exists():
            raise TestSeriesError("No such series found: '{}' at '{}'"
                                  .format(series_id, series_path))

        loader = SeriesConfigLoader()
        try:
            with (series_path/common.CONFIG_FN).open() as config_file:
                try:
                    series_cfg = loader.load(config_file)
                except (IOError, YAMLError, KeyError, ValueError, RequiredError) as err:
                    raise TestSeriesError(
                        "Error loading config for test series '{}'"
                        .format(sid), err)
        except OSError as err:
            raise TestSeriesError("Could not load config file for test series '{}': {}"
                                  .format(sid), err)

        series = cls(pav_cfg, _id=series_id, series_cfg=series_cfg, outfile=outfile)
        return series

    def _create_test_sets(self, iteration=0):
        """Create test sets from the config, and set up their dependency
        relationships. This is meant to be called by 'run()', but may be used
        separately for unit testing."""

        if self.test_sets:
            raise RuntimeError("_create_test_sets should only run when there are "
                               "no test sets for a series, but this series has: {}"
                               .format(self.test_sets))

        sets_path = self.path/'test_sets'
        sets_path.mkdir(exist_ok=True)

        # What each test depends on.
        depends_on = {}
        depended_on_by = defaultdict(set)

        # create all TestSet objects
        universal_modes = self.config['modes']
        for set_name, set_info in self.config['test_sets'].items():
            # Checks if the simultaneous key is set inside the test_set, if so, simultaneous limit
            # set in the test_set will override the simultaneous key at the full series level
            if set_info['simultaneous']:
                _simultaneous = set_info['simultaneous']
            else:
                _simultaneous = self.simultaneous

            set_obj = TestSet(
                pav_cfg=self.pav_cfg,
                name=set_name,
                test_names=set_info['tests'],
                iteration=iteration,
                modes=universal_modes + set_info['modes'],
                op_sys=self.config.get('os'),
                host=self.config.get('host'),
                only_if=set_info['only_if'],
                not_if=set_info['not_if'],
                parents_must_pass=set_info['depends_pass'],
                overrides=self.config.get('overrides', []),
                status=self.status,
                simultaneous= _simultaneous,
                outfile=self.outfile,
                verbosity=self.verbosity,
                ignore_errors=self.ignore_errors,
            )
            self._add_test_set(set_obj)

            depends_on[set_name] = set_info['depends_on']
            for parent in set_info['depends_on']:
                depended_on_by[parent].add(set_name)

        previous = None
        for set_name, test_set in self.test_sets.items():
            test_set = self.test_sets[set_name]
            for parent in depends_on[set_name]:
                if parent not in self.test_sets:
                    raise TestSeriesError(
                        "Test Set '{}' depends on '{}', but no such test set "
                        "exists.".format(set_name, parent))
                test_set.add_parents(self.test_sets[parent])

            if self.config['ordered'] and previous:
                test_set.add_parents(previous)

            previous = test_set

        # TODO: I goofed and coded ordering to be within a set. Maybe we'll want that
        #       feature eventually though.
        # If tests are implicitly ordered within sets, split each test set
        # into a set for each given test name.
        # if str_bool(self.config['ordered']):
        #    all_sets = list(self.test_sets.items())
        #    for set_name, test_set in all_sets:
        #        new_sets = test_set.ordered_split()
        #        del self.test_sets[set_name]
        #        for new_set in new_sets:
        #            self.test_sets[new_set.name] = new_set

        # Check for circular dependencies
        non_circular = []
        found_root = True
        test_sets = list(self.test_sets.values())

        while found_root and test_sets:
            found_root = False
            for test_set in list(test_sets):
                for parent_set in test_set.parent_sets:
                    if parent_set.name not in non_circular:
                        break
                else:
                    # Only do this if all of the parent sets are non_circular,
                    # which includes the case where a test set has no parents.
                    non_circular.append(test_set.name)
                    test_sets.remove(test_set)
                    found_root = True

        if test_sets:
            raise TestSeriesError(
                "The following sub-series have circular sub-series dependencies:\n{}"
                .format('\n'.join([ts.name for ts in test_sets])))

    def reset_test_sets(self):
        """Reset the series test sets, typically so that the series can be repeated.
        This does not preserve any manually added tests sets."""

        self.test_sets = {}

    def cancel(self, message=None, cancel_tests=True):
        """Goes through all test objects assigned to series and cancels tests
        that haven't been completed.

        :param message: Reason to give for cancellation.
        :param cancel_tests: Whether to cancel the attached tests. (Default True)
        """

        if self.pgid and self.pgid != os.getpid():
            try:
                os.killpg(self.pgid, signal.SIGTERM)
            except ProcessLookupError:
                pass

        if cancel_tests:
            for test in self.tests.values():
                test.cancel(message or "Cancelled via series. Reason not given.")

            cancel_utils.cancel_jobs(self.pav_cfg, List[self.tests.values()])

        self.status.set(SERIES_STATES.CANCELED, "Series cancelled: {}".format(message))

    def run(self, build_only: bool = False, rebuild: bool = False,
            local_builds_only: bool = False):
        """Build and kickoff all of the test sets in the series.

        :param build_only: Only build the tests, do not run them.
        :param rebuild: Rebuild tests instead of relying on cached builds.
        :param local_builds_only: When building, only build the tests that would build
            locally.
        :return:
        """

        self.status.set(SERIES_STATES.RUN, "Series running.")

        # create the test sets and link together.
        try:
            self._create_test_sets()
        except TestSeriesError as err:
            fprint(self.outfile, "Error creating test sets:\n{}".format(err.args[0]))
            self.status.set(SERIES_STATES.ERROR,
                            "Error creating test sets: {}".format(err.args[0]))
            raise

        # The names of all test sets that have completed.
        complete = set()  # type: Set[str]

        repeat = self.repeat

        simultaneous = self.config['simultaneous']
        if simultaneous == 0:
            simultaneous = None

        potential_sets = list(self.test_sets.values())

        repeat_iteration = 0

        # run sets in order
        while potential_sets:

            sets_to_run = []  # type: List[TestSet]

            # kick off any sets that aren't waiting on any sets to complete
            for test_set in potential_sets:
                parent_names = [parent.name for parent in test_set.parent_sets]
                if all(map(lambda par: par in complete, parent_names)):
                    sets_to_run.append(test_set)

            for test_set in sets_to_run:
                # Make sure it's ok to run this test set based on parent status.
                if not test_set.should_run:
                    test_set.mark_completed()
                    output.fprint(self.outfile, "Skipping test set '{}' due to parents not passing."
                                  .format(test_set.name))
                    continue

                try:
                    self._run_set(test_set, build_only=build_only,
                                  rebuild=rebuild, local_builds_only=local_builds_only)
                except TestSetError as err:
                    self.status.set(SERIES_STATES.ERROR,
                                    "Error running test set {}. See the series log "
                                    "`pav log series {}`.  {}"
                                    .format(test_set.name, self.sid, err.args[0]))

                    self.set_complete()
                    raise TestSeriesError(
                        "Error making tests for series '{}'."
                        .format(self.sid), err)

            for test_set in sets_to_run:
                potential_sets.remove(test_set)

            repeat -= 1

            if not potential_sets and repeat:
                # If we're repeating multiple times, reset the test sets for the series
                # and recreate them to run again.
                repeat_iteration += 1

                self.reset_test_sets()
                self._create_test_sets(repeat_iteration)
                potential_sets = list(self.test_sets.values())

        self.status.set(SERIES_STATES.ALL_STARTED,
                        "All {} tests have been started.".format(len(self.tests)))
        common.set_all_started(self.path)

        # Completion will be set when looked for.


    def _run_set(self, test_set: TestSet, build_only: bool, rebuild: bool,
         local_builds_only: bool, show_tracebacks: bool = False):
        """Run all requested tests in the given test set."""

        # Track which builds we've already marked as deprecated, when doing rebuilds.
        deprecated_builds = set()
        failed_builds = dict()
        tests_running = 0

        for test_batch in test_set.make_iter(build_only, rebuild, local_builds_only, show_tracebacks):

            # Add all the tests we created to this test set.
            self._add_tests(test_batch, test_set.iter_name)

            # Build each test
            try:
                test_set.build(deprecated_builds, failed_builds)
            except TestSetError as err:
                self.status.set(SERIES_STATES.BUILD_ERROR,
                                "Error building tests. See the series log `pav log series {}"
                                .format(self.sid))
                self.set_complete()
                raise TestSeriesError(
                    "Error building tests for series '{}'"
                    .format(self.sid), err)

            if not test_set.ready_to_start:
                continue

            try:
                started_tests, new_jobs = test_set.kickoff(show_tracebacks)
                tests_running += len(started_tests)
            except TestSetError as err:
                self.status.set(SERIES_STATES.KICKOFF_ERROR,
                                "Error kicking off tests for series '{}'".format(self.sid))
                raise TestSeriesError(
                    "Error kicking off tests for series '{}'".format(self.sid))

            if self.verbosity != Verbose.QUIET:
                if len(new_jobs) == 1:
                    fprint(self.outfile, "Kicked off a job for test set '{}' in series {}."
                                         .format(test_set.name, self.sid))
                else:
                    ktests = ', '.join([test.name for test in started_tests[:3]]
                                       + ['...'] if len(started_tests) > 3 else [])

                    fprint(self.outfile, "Kicked off tests {} ({} total) for test set {} "
                                         "in series {}."
                                         .format(ktests, len(started_tests),
                                                 test_set.name, self.sid))
            # If simultaneous is set in the test_set, use that.
            _simultaneous = test_set.simultaneous if test_set.simultaneous else self.simultaneous
            # Wait for jobs until enough have finished to start a new batch.
            while tests_running + self.batch_size > _simultaneous:
                tests_running -= test_set.wait()


    WAIT_INTERVAL = 0.5

    def wait(self, timeout=None):
        """Wait for the series to be complete or the timeout to expire. """

        if timeout is None:
            end = math.inf
        else:
            end = time.time() + timeout
        while time.time() < end:
            if self.complete:
                return
            time.sleep(2)

        raise TimeoutError("Series {} did not complete before timeout."
                           .format(self._id))

    @property
    def complete(self) -> bool:
        """Check if every test in the series has completed. A series is incomplete if
        no tests have been created."""

        complete_info = common.get_complete(self.pav_cfg, self.path, check_tests=True)

        return complete_info is not None

    def set_complete(self):
        """Write a file in the series directory that indicates that the series
        has finished."""

        # May raise a TestSeriesError
        common.set_complete(self.path)

    def info(self) -> SeriesInfo:
        """Return the series info object for this test. Note that this is super
        inefficient - the series info object exists to get series info without
        loading the series."""

        return SeriesInfo(self.pav_cfg, self.path)

    @property
    def pgid(self) -> Union[int, None]:
        """Returns pgid of series if it exists, None otherwise."""

        if self._pgid is None:

            pgid_path = self.path/self.PGID_FN

            if not pgid_path.exists():
                return None
            try:
                with open(str(pgid_path), 'r') as pgid_file:
                    pgid = pgid_file.read().strip()
            except OSError:
                return None

            try:
                self._pgid = int(pgid)
            except ValueError:
                return None

        return self._pgid

    def add_test_set_config(
            self, name, test_names: List[str], modes: List[str] = None,
            only_if: Dict[str, List[str]] = None,
            not_if: Dict[str, List[str]] = None,
            simultaneous: int = None,
            save: bool = True,
            _depends_on: List[str] = None, _depends_pass: bool = False):
        """Manually add a test set to this series. The set will be added to the
        series config, and created when we create all sets for the series. After
        adding all set configs, call save_config to update the saved config.

        :param name: The name of the test set.
        :param test_names: A list of test names (suite.name or name)
        :param modes: A List of modes to add.
        :param only_if: Only if conditions
        :param not_if:  Not if conditions
        :param simultaneous: Number of tests within the test set to run simultaneously.
        :param save: Save the series config after adding the test set. Setting this
            to false is useful if you want to add multiple configs before saving.
        :param _depends_on: A list of test names that this test depends on. For
            unit testing only.
        :param _depends_pass: Whether running this test set depends on it's parents
            passing. For unit testing only.
        """

        if name in self.config['test_sets']:
            raise TestSeriesError("A test set called '{}' already exists in series {}"
                                  .format(name, self.sid))

        self.config['test_sets'][name] = {
            'tests': test_names,
            'depends_pass': _depends_pass,
            'depends_on': _depends_on or [],
            'modes': modes or [],
            'only_if': only_if or {},
            'not_if': not_if or {},
            'simultaneous': simultaneous,
        }

        if save:
            self.save_config()

    def _add_test_set(self, test_set):
        """Add a test set to this series."""

        if test_set.name in self.test_sets:
            raise RuntimeError("Test set names must be unique within a series.")

        self.test_sets[test_set.name] = test_set

    def _add_tests(self, tests, test_set_name):
        """Add the tests in the test set to known series tests.

        :param test_set: The set of tests to add.
        """

        for test in tests:
            self._add_test(test_set_name, test)

    def _add_test(self, test_set_name: str, test: TestRun):
        """Add the given test to the series."""

        set_path = self.path/'test_sets'/test_set_name
        try:
            set_path.mkdir(exist_ok=True, parents=True)
        except OSError as err:
            raise TestSeriesError(
                "Could not create test set directory {} under series {}."
                .format(set_path, self.sid), err)

        # attempt to make symlink
        link_path = dir_db.make_id_path(set_path, test.id)

        self.tests[test.id_pair] = test

        # Create a symlink from each test to its series
        (test.path/'series').symlink_to(self.path)

        if not link_path.exists():
            try:
                link_path.symlink_to(test.path)
            except OSError as err:
                raise TestSeriesError(
                    "Could not link test '{}' in series at '{}'"
                    .format(test.path, link_path), err)

    def _save_series_id(self):
        """Save the series id to json file that tracks last series ran by user
        on a per system basis."""

        svars = sys_vars.get_vars(True)
        sys_name = svars['sys_name']

        json_file = self.pav_cfg.working_dir/'users'
        json_file /= '{}.json'.format(utils.get_login())

        lockfile_path = json_file.with_suffix('.lock')

        with LockFile(lockfile_path):
            data = {}
            try:
                with json_file.open() as json_series_file:
                    try:
                        data = json.load(json_series_file)
                    except json.decoder.JSONDecodeError:
                        # File was empty, therefore json couldn't be loaded.
                        pass
                with json_file.open('w') as json_series_file:
                    data[sys_name] = self.sid
                    json_series_file.write(json.dumps(data))

            except FileNotFoundError:
                # File hadn't been created yet.
                with json_file.open('w') as json_series_file:
                    data[sys_name] = self.sid
                    json_series_file.write(json.dumps(data))

    @property
    def timestamp(self):
        """Return the unix timestamp for this series, based on the last
modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return self.path.stat().st_mtime
