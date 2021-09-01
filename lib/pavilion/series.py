"""Series are a collection of test runs."""

import json
import logging
import os
import subprocess
import time
from collections import defaultdict
from pathlib import Path
from typing import List, Dict, Set, Tuple, Union, TextIO

from pavilion import dir_db
from pavilion import output
from pavilion import schedulers
from pavilion import system_variables
from pavilion import utils
from pavilion.lockfile import LockFile
from pavilion.output import fprint
from pavilion.series_config import SeriesConfigLoader
from pavilion.series_util import TestSeriesError, TestSeriesWarning
from pavilion.status_file import STATES
from pavilion.test_run import (
    TestRun, TestRunError)
from pavilion.test_set import TestSet, TestSetError
from pavilion.utils import str_bool
from yaml_config import YAMLError, RequiredError


class TestSeries:
    """Series are a well defined collection of tests, potentially with
    relationships, skip conditions, and other features by test set. The test runs
    in a series include all tests that have been created for that series, but not
    necessarily all tests that will be created. These are often organized into
    TestSets while being manipulated, but generally simply stored as a symlink to the
    test run directory between Pavilion instantiations."""

    LOGGER_FMT = 'series({})'
    SERIES_COMPLETE_FN = 'SERIES_COMPLETE'
    SERIES_PGID_FN = 'series.pgid'
    SERIES_OUT_FN = 'series.out'
    CONFIG_FN = 'config'
    DEPENDENCY_FN = 'dependency'

    def __init__(self, pav_cfg, _id=None,
                 series_config=None, dep_graph=None, overrides=None):
        """Initialize the series. Test sets may be added via 'add_tests()'.

        :param pav_cfg: The pavilion configuration object.
        :param _id: The test id number. If this is given, it implies that
            we're regenerating this series from saved files.
        :param series_config: Series config, if generated from a series file.
        :param dep_graph: The saved dependency graph (when loading).
        """

        self.pav_cfg = pav_cfg
        self.tests = {}  # type: Dict[Tuple[Path, int], TestRun]
        self.config = series_config or SeriesConfigLoader().load_empty()
        if not dep_graph:
            self.dep_graph = {}
        else:
            self.dep_graph = dep_graph
        self.test_sets = {}  # type: Dict[str, TestSet]
        self.overrides = overrides

        series_path = self.pav_cfg.working_dir/'series'

        self.simultaneous = series_config['simultaneous']
        self.repeat = series_config['repeat']

        self._pgid = None

        # We're creating this series from scratch.
        if _id is None:
            # Get the series id and path.
            try:
                self._id, self.path = dir_db.create_id_dir(series_path)
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}': {}"
                    .format(series_path, err))

            # save series config
            self.save_config()

            # Update user.json to record last series run per sys_name
            self._save_series_id()

        # We're not creating this from scratch (an object was made ahead of
        # time).
        else:
            self._id = _id
            self.path = dir_db.make_id_path(series_path, self._id)

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self._id))

    def run_background(self):
        """Run pav _series in background using subprocess module."""

        # start subprocess
        temp_args = ['pav', '_series', self.sid]
        try:
            series_out_path = self.path/self.SERIES_OUT_FN
            with series_out_path.open('w') as series_out:
                series_proc = subprocess.Popen(temp_args,
                                               stdout=series_out,
                                               stderr=series_out)

        except OSError as err:
            raise TestSeriesError("Could start series in background: {}"
                                  .format(err.args[0]))

        # write pgid to a file (atomically)
        series_pgid = os.getpgid(series_proc.pid)
        series_pgid_path = self.path/self.SERIES_PGID_FN
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

        series_config_path = self.path/self.CONFIG_FN
        try:
            series_config_tmp = series_config_path.with_suffix('.tmp')
            with series_config_tmp.open('w') as config_file:
                config_file.write(json.dumps(self.config))

            series_config_path.with_suffix('.tmp').rename(series_config_path)
        except OSError:
            fprint("Could not write series config to file. Cancelling.",
                   color=output.RED)

    WAIT_INTERVAL = 1

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
    def load(cls, pav_cfg, sid: str):
        """Load a series object from the given id, along with all of its
    associated tests.

    :raises TestSeriesError: From invalid series id or path."""

        series_id = cls.sid_to_id(sid)

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, series_id)

        if not series_path.exists():
            raise TestSeriesError("No such series found: '{}' at '{}'"
                                  .format(series_id, series_path))

        logger = logging.getLogger(cls.LOGGER_FMT.format(series_id))

        tests = []
        for path in dir_db.select(series_path, use_index=False).paths:
            try:
                test_id = int(path.name)
            except ValueError:
                series_info_files = [cls.SERIES_OUT_FN,
                                     cls.SERIES_PGID_FN,
                                     cls.CONFIG_FN,
                                     cls.DEPENDENCY_FN]
                if path.name not in series_info_files:
                    logger.info("Bad test id in series from dir '%s'", path)
                continue

            try:
                working_dir = path.resolve().parents[1]
            except FileNotFoundError as err:
                logger.info("Bad test id in series %s: %s", sid, err.args[0])
                continue

            try:
                test = TestRun.load(pav_cfg, working_dir, test_id)
                tests.append(test)
            except TestRunError as err:
                logger.info("Error loading test %s: %s",
                            test_id, err.args[0])

        loader = SeriesConfigLoader()
        try:
            with (series_path/cls.CONFIG_FN).open() as config_file:
                try:
                    config = loader.load(config_file)
                except (IOError, YAMLError, KeyError, ValueError, RequiredError) as err:
                    raise TestSeriesError(
                        "Error loading config for test series '{}': {}"
                        .format(sid, err.args[0]))
        except OSError as err:
            raise TestSeriesError("Could not load config file for test series '{}': {}"
                                  .format(sid, err.args[0]))

        return cls(pav_cfg, _id=series_id, series_config=config)

    def create_test_sets(self):
        """Create test sets from the config, and set up their dependency
        relationships."""

        # What each test depends on.
        depends_on = {}
        depended_on_by = defaultdict(lambda: set())

        # create all TestSet objects
        universal_modes = self.config['modes']
        for set_name, set_info in self.config['series'].items():
            set_obj = TestSet(
                pav_cfg=self.pav_cfg,
                name=set_name,
                test_names=set_info['tests'],
                modes=universal_modes + set_info['modes'],
                host=self.config['host'],
                only_if=set_info['only_if'],
                not_if=set_info['not_if'],
                parents_must_pass=set_info['depends_pass']
            )
            self._add_test_set(set_obj)

            depends_on[set_name] = set_info['depends_on']
            for parent in set_info['depends_on']:
                depended_on_by[parent].add(set_name)

        for set_name, test_set in self.test_sets.items():
            test_set = self.test_sets[set_name]
            parents = []
            for parent in depends_on[set_name]:
                if parent not in self.test_sets:
                    raise TestSeriesError(
                        "Test sub-series '{}' depends on '{}', but no such sub-series "
                        "exists.".format(set_name, parent))
                parents.append(self.test_sets[parent])

            children = []
            for child in depended_on_by[set_name]:
                # Children test sets are guaranteed to exist and missing ones are
                # detected when looking for parents
                children.append(self.test_sets[child])

            test_set.set_dependencies(parents, children)

        # If tests are implicitly ordered within sets, split each test set
        # into a set for each given test name.
        if str_bool(self.config['ordered']):
            all_sets = list(self.test_sets.items())
            for set_name, test_set in all_sets:
                new_sets = test_set.ordered_split()
                del self.test_sets[set_name]
                for new_set in new_sets:
                    self.test_sets[new_set.name] = new_set

        # Check for circular dependencies
        non_circular = []
        found_root = True
        test_sets = list(self.test_sets.values())
        while found_root and test_sets:
            found_root = False
            for test_set in list(test_sets):
                for pset in test_set.parent_sets:
                    if pset.name not in non_circular:
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

    def reset(self):
        """Reset the series test sets, typically so that the series can be repeated.
        This does not preserve any manually added tests sets."""

        self.test_sets = {}

    def cancel(self, message=None):
        """Goes through all test objects assigned to series and cancels tests
        that haven't been completed. """

        for test_obj in self.tests.values():
            if test_obj.complete:
                sched = schedulers.get_plugin(test_obj.scheduler)
                sched.cancel_job(test_obj)
                test_obj.status.set(STATES.COMPLETE, message)
                test_obj.set_run_complete()

    def run(self, build_only: bool = False, rebuild: bool = False,
            verbosity: int = 0, outfile: TextIO = None):
        """Build and kickoff all of the test sets in the series.

        :param build_only: Only build the tests, do not run them.
        :param rebuild: Rebuild tests instead of relying on cached builds.
        :param verbosity: Verbosity level. 0 - rolling summaries,
            1 - continuous summary, 2 - full verbose
        :param outfile: The outfile to write status info to.
        :return:
        """

        if outfile is None:
            outfile = open('/dev/null', 'w')

        # create the test sets and link together.
        self.create_test_sets()

        # The names of all test sets that have completed.
        complete = set()  # type: Set[str]

        simultaneous = self.config['simultaneous']
        if simultaneous == 0:
            simultaneous = None

        potential_sets = list(self.test_sets.values())

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
                if not test_set.should_run():
                    continue

                # Create the test objects
                try:
                    test_set.make(build_only, rebuild, outfile=outfile)
                except TestSetError as err:
                    raise TestSeriesError(
                        "Error making tests for series '{}': {}"
                        .format(self.sid, err.args[0]))

                # Add all the tests we created to this test set.
                self._add_tests(test_set)

                # Build each test
                try:
                    test_set.build(verbosity=verbosity, outfile=outfile)
                except TestSetError as err:
                    raise TestSeriesError(
                        "Error building tests for series '{}': {}"
                        .format(self.sid, err.args[0]))

                test_start_count = simultaneous
                while not test_set.done:
                    try:
                        test_set.kickoff(test_start_count)
                    except TestSetError as err:
                        raise TestSeriesError(
                            "Error in series '{}': {}".format(self.sid, err.args[0]))

                    test_start_count = test_set.wait(simultaneous)

            for test_set in sets_to_run:
                potential_sets.remove(test_set)

    def wait(self, timeout=None):
        """Wait for the series to be complete or the timeout to expire. """

        end = time.time() + timeout
        while time.time() < end:
            if (self.path/self.SERIES_COMPLETE_FN).exists():
                return
            time.sleep(0.1)

        raise TimeoutError("Series {} did not complete before timeout."
                           .format(self._id))

    def set_series_complete(self):
        """Write a file in the series directory that indicates that the series
        has finished."""

        series_complete_path = self.path/self.SERIES_COMPLETE_FN
        series_complete_path_tmp = series_complete_path.with_suffix('.tmp')
        with series_complete_path_tmp.open('w') as series_complete:
            json.dump({'complete': time.time()}, series_complete)

        series_complete_path_tmp.rename(series_complete_path)

    @property
    def pgid(self) -> Union[int, None]:
        """Returns pgid of series if it exists, None otherwise."""

        if self._pgid is None:

            pgid_path = self.path/self.SERIES_PGID_FN

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

    def add_test_set_config(self, name, test_names: List[str], modes: List[str] = None,
                            host: str = None, overrides: List[str] = None):
        """Manually add a test set to this series. The set will be added to the
        series config, and created when we create all sets for the series. After
        adding all set configs, call save_series_config to update the saved config."""

        if name in self.config['series']:
            raise TestSeriesError("A test set called '{}' already exists in series {}"
                                  .format(name, self.sid))

        self.config['series'][name] = {
            'tests': test_names,
            'depends_pass': False,
            'depends_on': [],
            'modes': modes or [],
            'host': host,
            'only_if': [],
            'not_if': [],
            'overrides': overrides,
        }

    def _add_test_set(self, test_set):
        """Add a test set to this series."""

        if test_set.name in self.test_sets:
            raise RuntimeError("Test set names must be unique within a series.")

        self.test_sets[test_set.name] = test_set

        if test_set.tests is not None:
            self._add_tests(test_set)

    def _add_tests(self, test_set: TestSet):
        """Add the tests in the test set to known series tests.

        :param test_set: The set of tests to add.
        """

        if test_set.tests is None:
            raise RuntimeError("You must run TestSet.make() on the test set before"
                               "it will have tests to add.")

        for test in test_set.tests:
            self.tests[(test.working_dir, test.id)] = test

            # attempt to make symlink
            link_path = dir_db.make_id_path(self.path, test.id)

            if link_path.exists():
                continue

            try:
                link_path.symlink_to(test.path)
            except OSError as err:
                raise TestSeriesError(
                    "Could not link test '{}' in series at '{}': {}"
                    .format(test.path, link_path, err))

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
