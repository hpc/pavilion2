"""Series are a collection of test runs."""

import datetime as dt
import json
import os
import pathlib
import time
import copy
import codecs
import subprocess
import sys
import signal
import logging
from pathlib import Path

from pavilion import dir_db
from pavilion import utils
from pavilion import commands
from pavilion import schedulers
from pavilion import test_config
from pavilion import system_variables
from pavilion import output
from pavilion import cmd_utils
from pavilion.test_config import resolver
from pavilion.status_file import STATES
from pavilion.builder import MultiBuildTracker
from pavilion.lockfile import LockFile
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


class TestSet:
    # need info like
    # modes, only/not_ifs, next, prev
    def __init__(self, name, tests, modes, only_if, not_if, pav_cfg,
                 series_obj):
        self.name = name
        # self.tests = tests
        self.tests = {} # { 'test_name': <test obj> }
        for test in tests:
            self.tests[test] = None
        self.modes = modes
        self.only_if = only_if
        self.not_if = not_if
        self.pav_cfg = pav_cfg
        self.series_obj = series_obj

        self._before = []
        self._after = []

        self.done = False
        self.all_pass = False

    @property
    def before(self):
        return self._before

    @before.setter
    def before(self, prev_tests):

        if isinstance(prev_tests, list):
            self._before.extend(prev_tests)
        elif isinstance(prev_tests, str):
            self._before.append(prev_tests)
        else:
            raise TestSeriesError("Something went wrong.")

    @property
    def after(self):
        return self._after

    @after.setter
    def after(self, next_tests):

        if isinstance(next_tests, list):
            self._after.extend(next_tests)
        elif isinstance(next_tests, str):
            self._after.append(next_tests)
        else:
            raise TestSeriesError("Something went wrong.")

    def run_set(self):

        # basically copy what the run command is doing here
        mb_tracker = MultiBuildTracker()

        run_cmd = commands.get_command('run')

        # run.RunCommand._get_tests function
        try:
            new_conditions = {
                'only_if': self.only_if,
                'not_if': self.not_if
            }

            # resolve configs
            configs_by_sched = cmd_utils.get_test_configs(
                pav_cfg=self.pav_cfg,
                host=None, # TODO: add hosts
                test_files=[],
                tests=self.tests,
                modes=self.modes,
                logger=None, # TODO: logger??????
                overrides=None,
                conditions=new_conditions,
            )

            # configs->tests
            tests_by_sched = cmd_utils.configs_to_tests(
                pav_cfg=self.pav_cfg,
                configs_by_sched=configs_by_sched,
                mb_tracker=mb_tracker,
                build_only=False,
                rebuild=False
            )

        except commands.CommandError as err:
            # probably won't happen
            err = codecs.decode(str(err), 'unicode-escape')
            return None

        except test_config.file_format.TestConfigError as err:
            return None

        if tests_by_sched is None:
            # probably won't happen but just in case
            return None

        all_tests = sum(tests_by_sched.values(), [])
        run_cmd.last_tests = list(all_tests)

        if not all_tests:
            # probalby won't happen but just in case
            return None

        # assign tests to series and vice versa
        self.series_obj.add_tests(all_tests)
        for test_obj in all_tests:
            self.tests[test_obj.name] = test_obj

        run_cmd.last_series = self.series_obj

        # make sure result parsers are ok
        res = run_cmd.check_result_format(all_tests)
        if res != 0:
            run_cmd.complete_tests(all_tests)
            return None

        # attempt to build
        res = cmd_utils.build_local(
            tests=all_tests,
            max_threads=self.pav_cfg.build_threads,
            mb_tracker=mb_tracker,
            build_verbosity=0,
            outfile=open(os.devnull, 'w'), # TODO: FIX THIS
            errfile=open(os.devnull, 'w')
        )
        if res != 0:
            run_cmd.complete_tests(all_tests)
            return None

        # deal with simultaneous here
        if self.series_obj.config['simultaneous'] is None:
            run_cmd.run_tests(
                pav_cfg=self.pav_cfg,
                tests_by_sched=tests_by_sched,
                series=self.series_obj,
                wait=None,
                report_status=False
            )
        else:
            simult = int(self.series_obj.config['simultaneous'])

            # [ { sched: test_obj }, { sched: test_obj }, etc. ]
            list_of_tests_by_sched = []
            for sched, test_objs in tests_by_sched.items():
                for test_obj in test_objs:
                    list_of_tests_by_sched.append({sched: [test_obj]})

            for test in list_of_tests_by_sched:
                self.test_wait(simult)
                run_cmd.run_tests(
                    pav_cfg=self.pav_cfg,
                    tests_by_sched=test,
                    series=self.series_obj,
                    wait=None,
                    report_status=False
                )

    def test_wait(self, simul):

        while len(self.series_obj.get_currently_running()) >= simul:
            time.sleep(0.1)

        return

    def is_done(self):

        all_tests_passed = True

        for test_name, test_obj in self.series_obj.tests.items():
            # check if test object even exists
            if test_obj is None:
                return False

            # update the status
            if test_obj._job_id:
                test_sched = schedulers.get_plugin(test_obj.scheduler)
                test_sched.job_status(self.pav_cfg, test_obj)

            # check if RUN_COMPLETE exists
            if not (test_obj.path/'RUN_COMPLETE').exists():
                return False

            # check if test passed
            try:
                if test_obj.results['result'] != 'PASS':
                    all_tests_passed = False
            except KeyError:
                all_tests_passed = False

        # if all_tests_passed is still True, update object variable
        self.all_pass = all_tests_passed

        self.done = True
        return True

    def skip_set(self):

        temp_resolver = resolver.TestConfigResolver(self.pav_cfg)
        raw_configs = temp_resolver.load_raw_configs(
            list(self.tests.keys()), [], self.modes
        )
        for config in raw_configs:
            # Delete conditionals - we're already skipping this test but for
            # different reasons
            del config['only_if']
            del config['not_if']
            skipped_test = TestRun(self.pav_cfg, config)
            skipped_test.status.set(STATES.SKIPPED,
                                    'Skipping. Previous test did not PASS.')
            skipped_test.set_run_complete()
            self.series_obj.add_tests([skipped_test])
            self.tests[skipped_test.name] = skipped_test

        self.done = True

    def kill_set(self):

        for test_name, test_obj in self.tests.items():
            if test_obj:
                test_obj.status.set(STATES.COMPLETE, "Killed by SIGTERM. ")
                test_obj.set_run_complete()


class TestSeries:
    """Series are a collection of tests. Every time """

    LOGGER_FMT = 'series({})'

    def __init__(self, pav_cfg, tests=None, _id=None, series_config=None,
                 dep_graph=None):
        """Initialize the series.

        :param pav_cfg: The pavilion configuration object.
        :param list tests: The list of test objects that belong to this series.
        :param int _id: The test id number. If this is given, it implies that
            we're regenerating this series from saved files.
        :param dict series_cfg: Series config, if generated from a series file.
        """

        self.pav_cfg = pav_cfg
        self.tests = {}
        self.config = series_config
        if not dep_graph:
            self.dep_graph = {}
        else:
            self.dep_graph = dep_graph
        self.test_sets = {} # { set_name: TestSetObject }
        self.test_objs = {}

        if tests:
            self.tests = {test.id: test for test in tests}

        series_path = self.pav_cfg.working_dir/'series'

        # We're creating this series from scratch.
        if _id is None:
            # Get the series id and path.
            try:
                self._id, self.path = dir_db.create_id_dir(series_path)
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}': {}"
                    .format(series_path, err))

            # Create self.dep_graph, apply ordered: True, check for circular
            # dependencies
            self.dep_graph = self.create_dependency_graph()
            self.save_dep_graph()

            # save series config
            self.save_series_config()

            # Create a soft link to the test directory of each test in the
            # series.
            if tests:
                for test in tests:
                    link_path = dir_db.make_id_path(self.path, test.id)

                    try:
                        link_path.symlink_to(test.path)
                    except OSError as err:
                        raise TestSeriesError(
                            "Could not link test '{}' in series at '{}': {}"
                            .format(test.path, link_path, err))

            # Update user.json to record last series run per sys_name
            self._save_series_id()

        # We're not creating this from scratch (an object was made ahead of
        # time).
        else:
            self._id = _id
            self.path = dir_db.make_id_path(series_path, self._id)
            self.dep_graph, self.config = self.load_dep_graph()

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self._id))

    def run_series_background(self):
        """Run pav _series in background using subprocess module."""

        # start subprocess
        temp_args = ['pav', '_series', str(self._id)]
        try:
            with open(str(self.path/'series.out'), 'w') as series_out:
                series_proc = subprocess.Popen(temp_args,
                                               stdout=series_out,
                                               stderr=series_out)
        except TypeError:
            series_proc = subprocess.Popen(temp_args,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL)
        except FileNotFoundError:
            output.fprint("Could not kick off tests. Cancelling.",
                          color=output.RED)
            return

        # write pgid to a file (atomically)
        series_pgid = os.getpgid(series_proc.pid)
        series_pgid_path = self.path/'series.pgid'
        try:
            with series_pgid_path.with_suffix('.tmp').open('w') as \
                    series_id_file:
                series_id_file.write(str(series_pgid))

            series_pgid_path.with_suffix('.tmp').rename(series_pgid_path)
            output.fprint("Started series s{}. "
                          "Run `pav status s{}` to view status. "
                          "PGID is {}. "
                          "To kill, use `kill -15 -{}` or `pav cancel s{}`."
                          .format(self._id,
                                  self._id,
                                  series_pgid,
                                  series_pgid,
                                  self._id))
        except TypeError:
            output.fprint("Warning: Could not write series PGID to a file.",
                          color=output.YELLOW)
            output.fprint("Started series s{}."
                          "Run `pav status s{}` to view status. "
                          "PGID is {}."
                          "To kill, use `kill -15 -s{}`."
                          .format(self._id,
                                  self._id,
                                  series_pgid,
                                  series_pgid))

    def get_currently_running(self):
        """Returns list of tests that have states of either SCHEDULED or
        RUNNING. """

        cur_run = []
        for test_id, test_obj in self.tests.items():
            temp_state = test_obj.status.current().state
            if temp_state in ['SCHEDULED', 'RUNNING']:
                cur_run.append(test_obj)
        return cur_run

    def save_series_config(self):
        """
        Saves series config to a file.
        :return:
        """

        series_config_path = self.path/'config'
        try:
            with series_config_path.with_suffix('.tmp').open('w') as \
                    config_file:
                config_file.write(json.dumps(self.config))

            series_config_path.with_suffix('.tmp').rename(series_config_path)
        except OSError:
            fprint("Could not write series config to file. Cancelling.",
                   color=output.RED)

    def create_dependency_graph(self):
        """
        Create self.dep_graph, apply ordered: True, check for circular
        dependencies.
        :return:
        """

        if not self.config:
            return

        dep_graph = {}

        # create dependency tree
        last_set_name = None
        is_ordered = self.config['ordered'] in ['True', 'true']
        for set_name, set_config in self.config['series'].items():
            dep_graph[set_name] = set_config['depends_on']

            if is_ordered and last_set_name is not None \
                    and last_set_name not in dep_graph[set_name]:
                dep_graph[set_name].append(last_set_name)

            last_set_name = set_name

        temp_original_dep = copy.deepcopy(dep_graph)

        # check for circular dependencies
        unresolved = list(dep_graph.keys())
        resolved = []

        while unresolved:
            resolved_something = False

            for unresolved_set in unresolved:
                # Find if there any dependencies are/were resolved
                temp_dep_list = copy.deepcopy(dep_graph[unresolved_set])
                for dep in dep_graph[unresolved_set]:
                    if dep in resolved:
                        temp_dep_list.remove(dep)
                dep_graph[unresolved_set] = temp_dep_list

                # If this was already fully resolved, add it to resolved
                if not dep_graph[unresolved_set]:
                    resolved.append(unresolved_set)
                    unresolved.remove(unresolved_set)
                    resolved_something = True

            if not resolved_something:
                break

        if unresolved:
            raise TestSeriesError(
                "Circular dependencies detected. Please fix. No tests are run.",
            )

        return temp_original_dep

    def save_dep_graph(self):
        """
        Write dependency tree and config in series dir
        :return:
        """

        series_dep_path = self.path/'dependency'
        try:
            with series_dep_path.with_suffix('.tmp').open('w') as dep_file:
                dep_file.write(json.dumps(self.dep_graph))

            series_dep_path.with_suffix('.tmp').rename(series_dep_path)
        except OSError:
            fprint("Could not write dependency tree to file. Cancelling.",
                   color=output.RED)

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

        return dir_db.select(series_path)

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
        for path in dir_db.select(series_path):
            try:
                test_id = int(path.name)
            except ValueError:
                series_info_files = ['series.out', 'series.pgid', 'config',
                                     'dependency']
                if path.name not in series_info_files:
                    logger.info("Bad test id in series from dir '%s'", path)
                continue

            try:
                tests.append(TestRun.load(pav_cfg, test_id=test_id))
            except TestRunError as err:
                logger.info("Error loading test %s: %s",
                            test_id, err.args[0])

        return cls(pav_cfg, tests, _id=sid)

    def load_dep_graph(self):
        """Load a series object from the given id, along with the config and
        dependency tree."""

        try:
            with (self.path/'dependency').open() as dep_file:
                dep = dep_file.readline()

            with (self.path/'config').open() as config_file:
                config = config_file.readline()

            return json.loads(dep), json.loads(config)

        except FileNotFoundError as fnfe:
            raise TestSeriesError("Files not found. {}".format(fnfe))

    def create_set_graph(self):
        """Create doubly linked list of TestSets and applies hosts and modes
        to them"""

        # create all TestSet objects
        universal_modes = self.config['modes']
        for set_name, set_info in self.config['series'].items():
            modes = universal_modes + set_info['modes']
            set_obj = TestSet(set_name, set_info['tests'], modes,
                              set_info['only_if'], set_info['not_if'],
                              self.pav_cfg, self)
            self.test_sets[set_name] = set_obj

        # create doubly linked graph of TestSet objects
        for set_name in self.dep_graph:
            self.test_sets[set_name].before = self.dep_graph[set_name]

            next_list = []
            for s_n in self.dep_graph:
                if set_name in self.dep_graph[s_n]:
                    next_list.append(s_n)
            self.test_sets[set_name].after = next_list

        return

    def run_series(self):

        # handles SIGTERM (15) signal
        def sigterm_handler(*args):

            for set_name in self.started:
                self.test_sets[set_name].kill_set()

            sys.exit()

        signal.signal(signal.SIGTERM, sigterm_handler)

        # run sets in order
        while True:

            self.all_sets = list(self.test_sets.keys())
            self.started = []
            self.waiting = []
            self.finished = []

            # kick off any sets that aren't waiting on any sets to complete
            for set_name, set_obj in self.test_sets.items():
                if not set_obj.before:
                    set_obj.run_set()
                    self.started.append(set_name)
                    self.waiting = list(set(self.all_sets) - set(self.started))

            while len(self.waiting) != 0:

                self.series_test_handler()
                time.sleep(0.1)

            self.update_finished_list()

            # if restart isn't necessary, break out of loop
            if self.config['restart'] not in ['True', 'true']:
                break
            else:
                # wait for all the tests to be finished to continue
                done = False
                while not done:
                    done = True
                    for set_name, set_obj in self.test_sets.items():
                        if not set_obj.is_done:
                            done = False
                            break
                    time.sleep(0.1)

                # create a whole new test sets dictionary
                if done:
                    self.create_set_graph()

    def update_finished_list(self):

        for set_name in self.started:
            if self.test_sets[set_name].is_done():
                self.finished.append(set_name)
                self.started.remove(set_name)

    def series_test_handler(self):

        self.update_finished_list()

        # logic on what needs to be done based on new information
        temp_waiting = copy.deepcopy(self.waiting)
        for set_name in temp_waiting:
            # check if all the sets this set depends on are finished
            ready = all(prev in self.finished for prev in self.test_sets[
                set_name].before)
            if ready:
                # this set requires that the sets it depends on passes
                if self.config['series'][set_name]['depends_pass'] in \
                        ['True', 'true']:
                    # all the tests passed, so run this test
                    if self.test_sets[set_name].all_pass:
                        self.tests_sets[set_name].run_set()
                        self.started.append(set_name)
                        self.waiting.remove(set_name)
                    # the tests didn't all pass, so skip this test
                    else:
                        self.test_sets[set_name].skip_set()
                        self.finished.append(set_name)
                        self.waiting.remove(set_name)
                else:
                    # All the sets completed and we don't care if they passed so
                    # run this set
                    self.test_sets[set_name].run_set()
                    self.started.append(set_name)
                    self.waiting.remove(set_name)

    @staticmethod
    def get_pgid(pav_cfg, id_):

        try:
            id_ = int(id_[1:])
        except TypeError as err:
            pass

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, int(id_))
        series_id_path = series_path/'series.pgid'

        if not series_id_path.exists():
            return False

        with open(str(series_id_path), 'r') as series_id_file:
            series_id = series_id_file.readline()

        try:
            series_id = int(series_id)
        except ValueError:
            return False

        return series_id

    def add_tests(self, test_objs):
        """
        Adds tests to existing series.
        :param test_objs: List of test objects
        :return: None
        """

        for test in test_objs:
            self.tests[test.id] = test

            # attempt to make symlink
            link_path = dir_db.make_id_path(self.path, test.id)

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
        self._tests = [tpath for tpath in dir_db.select(self.path)]

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

