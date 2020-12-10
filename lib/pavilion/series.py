"""Series are a collection of test runs."""

import copy
import errno
import json
import logging
import os
import signal
import subprocess
import sys
import time
from io import StringIO
from typing import List, Dict, TextIO, Union

from pavilion import cmd_utils
from pavilion import commands
from pavilion import dir_db
from pavilion import output
from pavilion import schedulers
from pavilion import system_variables
from pavilion import test_config
from pavilion import utils
from pavilion.builder import MultiBuildTracker
from pavilion.lockfile import LockFile
from pavilion.output import fprint
from pavilion.permissions import PermissionsManager
from pavilion.series_util import TestSeriesError
from pavilion.status_file import STATES
from pavilion.test_config import resolver
from pavilion.test_run import (
    TestRun, TestRunError)
from pavilion.utils import str_bool


class TestSet:
    """Class describes a set of tests."""

    LOGGER_FMT = 'series({})'

    # need info like
    # modes, only/not_ifs, next, prev
    def __init__(self, pav_cfg, name: str, tests: List[str], modes: List[str],
                 host: str, only_if: Dict[str, List[str]],
                 not_if: Dict[str, List[str]], series_obj: 'TestSeries'):
        self.name = name
        self.tests = {}  # type: Dict[str, TestRun]
        self._test_names = tests
        self.modes = modes
        self.host = host
        self.only_if = only_if
        self.not_if = not_if
        self.pav_cfg = pav_cfg
        self.series_obj = series_obj

        self.before = set()
        self.after = set()

        self.done = False
        self.all_pass = False

        self.logger = logging.getLogger(
            self.LOGGER_FMT.format(self.series_obj._id))

        self.outfile = series_obj.outfile
        self.errfile = series_obj.errfile

    def run_set(self):
        """Runs tests in set. """

        mb_tracker = MultiBuildTracker(log=False)

        run_cmd = commands.get_command('run')

        # run.RunCommand._get_tests function
        try:
            new_conditions = {
                'only_if': self.only_if,
                'not_if': self.not_if
            }

            # resolve configs
            test_configs = cmd_utils.get_test_configs(
                pav_cfg=self.pav_cfg,
                host=self.host,
                tests=self._test_names,
                modes=self.modes,
                outfile=self.outfile,
                conditions=new_conditions,
            )

            # configs->tests
            test_list = cmd_utils.configs_to_tests(
                pav_cfg=self.pav_cfg,
                proto_tests=test_configs,
                mb_tracker=mb_tracker,
                outfile=self.outfile,
            )

        except (commands.CommandError, test_config.TestConfigError) as err:
            self.done = True
            output.fprint("Error resolving configs. \n{}".format(err.args[0]),
                          file=self.errfile, color=output.RED)
            return None

        if not test_list:
            self.done = True
            self.all_pass = True
            return None

        all_tests = test_list
        run_cmd.last_tests = all_tests

        # assign tests to series and vice versa
        self.series_obj.add_tests(all_tests)
        for test_obj in all_tests:
            self.tests[test_obj.name] = test_obj

        run_cmd.last_series = self.series_obj

        # make sure result parsers are ok
        res = cmd_utils.check_result_format(all_tests, self.errfile)
        if res != 0:
            self.done = True
            cmd_utils.complete_tests(all_tests)
            return None

        # attempt to build
        res = cmd_utils.build_local(
            tests=all_tests,
            max_threads=self.pav_cfg.build_threads,
            mb_tracker=mb_tracker,
            outfile=self.outfile,
            errfile=self.errfile
        )
        if res != 0:
            self.done = True
            cmd_utils.complete_tests(all_tests)
            return None

        # deal with simultaneous here
        if self.series_obj.config['simultaneous'] is None:
            self.series_obj.run_tests(tests=all_tests)
        else:
            simult = int(self.series_obj.config['simultaneous'])

            for test in all_tests:
                self.test_wait(simult)
                self.series_obj.run_tests(tests=[test])

    def test_wait(self, simul):
        """Returns when the number of tests running is less than or equal to
        the number of tests that can run or be scheduled simultaneously,
        if the simultaneous parameter is set. """

        while len(self.series_obj.get_currently_running()) >= simul:
            time.sleep(0.1)

        return

    def is_done(self):
        """Returns True if all the tests in the set are completed."""

        if self.done:
            return True

        all_tests_passed = True

        for test_name, test_obj in self.series_obj.tests.items():
            # check if test object even exists
            if test_obj is None:
                return False

            # update the status
            if test_obj.job_id:
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
        """Procedure to skip tests. """

        temp_resolver = resolver.TestConfigResolver(self.pav_cfg)
        raw_configs = temp_resolver.load_raw_configs(
            list(self.tests.keys()), [], self.modes
        )
        for config in raw_configs:
            # Delete conditionals - we're already skipping this test but for
            # different reasons
            skipped_test = TestRun(self.pav_cfg, config)
            skipped_test.set_skipped('Previous test in series did not PASS.')
            skipped_test.save_attributes()
            self.series_obj.add_tests([skipped_test])
            self.tests[skipped_test.name] = skipped_test

        self.done = True

    def kill_set(self):
        """Goes through all the tests assigned to set and kills tests. """

        for test_name, test_obj in self.tests.items():
            if test_obj:
                test_obj.status.set(STATES.COMPLETE, "Killed by SIGTERM. ")
                test_obj.set_run_complete()


DEPENDENCY_FN = 'dependency'
CONFIG_FN = 'config'
SERIES_OUT_FN = 'series.out'
SERIES_PGID_FN = 'series.pgid'


class TestSeries:
    """Series are a well defined collection of tests, potentially with
    relationships, skip conditions, and other features by test set."""

    LOGGER_FMT = 'series({})'

    def __init__(self, pav_cfg, tests=None, _id=None, series_config=None,
                 dep_graph=None, outfile: TextIO = StringIO(),
                 errfile: TextIO = StringIO()):
        """Initialize the series.

        :param pav_cfg: The pavilion configuration object.
        :param list tests: The list of test objects that belong to this series.
        :param _id: The test id number. If this is given, it implies that
            we're regenerating this series from saved files.
        :param series_config: Series config, if generated from a series file.
        :param dep_graph: The saved dependency graph (when loading).
        :param outfile: Where to send user output.
        :param errfile: Where to send user error output.
        """

        self.pav_cfg = pav_cfg
        self.outfile = outfile
        self.errfile = errfile
        self.tests = {}
        self.config = series_config
        if not dep_graph:
            self.dep_graph = {}
        else:
            self.dep_graph = dep_graph
        self.test_sets = {}  # type: Dict[str, TestSet]
        self.test_objs = {}

        if tests:
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

            # Create self.dep_graph, apply ordered: True, check for circular
            # dependencies
            self.dep_graph = self.create_dependency_graph()
            self.save_dep_graph()

            # save series config
            self.save_series_config()

            perm_man = PermissionsManager(None, pav_cfg['shared_group'],
                                          pav_cfg['umask'])

            # Create a soft link to the test directory of each test in the
            # series.
            if tests:
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
        temp_args = ['pav', '_series', self.sid]
        try:
            series_out_path = self.path/SERIES_OUT_FN
            with PermissionsManager(series_out_path,
                                    self.pav_cfg['shared_group'],
                                    self.pav_cfg['umask']), \
                    series_out_path.open('w') as series_out:
                series_proc = subprocess.Popen(temp_args,
                                               stdout=series_out,
                                               stderr=series_out)

        except OSError as err:
            output.fprint("Could not kick off tests. Cancelling. \n{}."
                          .format(err.args[0]),
                          file=self.errfile, color=output.RED)
            return

        # write pgid to a file (atomically)
        series_pgid = os.getpgid(series_proc.pid)
        series_pgid_path = self.path/SERIES_PGID_FN
        try:
            series_pgid_tmp = series_pgid_path.with_suffix('.tmp')
            with PermissionsManager(series_pgid_tmp,
                                    self.pav_cfg['shared_group'],
                                    self.pav_cfg['umask']), \
                    series_pgid_tmp.open('w') as series_id_file:
                series_id_file.write(str(series_pgid))

            series_pgid_tmp.rename(series_pgid_path)
        except OSError as err:
            output.fprint("Warning: Could not write series PGID to a file.\n"
                          "To cancel, use `kill -14 -s{pgid}\n{err}"
                          .format(err=err.args[0], pgid=series_pgid),
                          color=output.YELLOW, file=self.outfile)
        output.fprint("Started series {sid}.\n"
                      "Run `pav status {sid}` to view status.\n"
                      "PGID is {pgid}.\nTo kill, use `pav cancel {sid}`."
                      .format(sid=self.sid, pgid=series_pgid),
                      file=self.outfile)

    def get_currently_running(self):
        """Returns list of tests that have states of either SCHEDULED or
        RUNNING. """

        cur_run = []
        for test_id, test_obj in self.tests.items():
            temp_state = test_obj.status.current().state
            if temp_state in ['SCHEDULED', 'RUNNING']:
                cur_run.append(test_obj)
        return cur_run

    def save_series_config(self) -> None:
        """Saves series config to a file."""

        series_config_path = self.path/CONFIG_FN
        try:
            series_config_tmp = series_config_path.with_suffix('.tmp')
            with PermissionsManager(series_config_tmp,
                                    self.pav_cfg['shared_group'],
                                    self.pav_cfg['umask']), \
                    series_config_tmp.open('w') as config_file:
                config_file.write(json.dumps(self.config))

            series_config_path.with_suffix('.tmp').rename(series_config_path)
        except OSError:
            fprint("Could not write series config to file. Cancelling.",
                   color=output.RED)

    def create_dependency_graph(self) -> Union[Dict, None]:
        """Create the dependency graph. Order is either explicit (through
        before and after) or implicit through the 'ordered' option."""

        if not self.config:
            return None

        dep_graph = {}

        # create dependency tree
        last_set_name = None
        is_ordered = str_bool(self.config['ordered'])
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
        """Write dependency tree and config in series dir

        :return:
        """

        series_dep_path = self.path/DEPENDENCY_FN
        series_dep_tmp = series_dep_path.with_suffix('.tmp')
        try:
            with PermissionsManager(series_dep_tmp,
                                    self.pav_cfg['shared_group'],
                                    self.pav_cfg['umask']), \
                  series_dep_tmp.open('w') as dep_file:
                dep_file.write(json.dumps(self.dep_graph))

            series_dep_path.with_suffix('.tmp').rename(series_dep_path)
        except OSError:
            fprint("Could not write dependency tree to file. Cancelling.",
                   color=output.RED, file=self.errfile)

    WAIT_INTERVAL = 1

    def run_tests(self, wait: Union[None, int] = None,
                  tests: List[TestRun] = None) -> int:
        """Run the tests for this test series.

    :param int wait: Wait this long for a test to start before exiting.
    :param tests: Manually specified list of tests to run. Defaults to
        the series' test list.
    :return: A return code based on the success of this action.
    """

        if tests is None:
            tests = list(self.tests.values())

        all_tests = tests

        for test in tests:
            sched_name = test.scheduler
            sched = schedulers.get_plugin(sched_name)

            if not sched.available():
                fprint("1 test started with the {} scheduler, but"
                       "that scheduler isn't available on this system."
                       .format(sched_name),
                       file=self.errfile, color=output.RED)
                return errno.EINVAL

        for test in tests:

            # don't run this test if it was meant to be skipped
            if test.skipped:
                continue

            # tests that are build-only or build-local should
            # already be completed, therefore don't run these

            if test.complete:
                continue

            sched = schedulers.get_plugin(test.scheduler)
            try:
                sched.schedule_tests(self.pav_cfg, [test])
            except schedulers.SchedulerPluginError as err:
                fprint('Error scheduling test: ', file=self.errfile,
                       color=output.RED)
                fprint(err, bullet='  ', file=self.errfile)
                fprint('Cancelling already kicked off tests.',
                       file=self.errfile)
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
                for test in tests:
                    sched = schedulers.get_plugin(test.scheduler)
                    status = test.status.current()
                    if status == STATES.SCHEDULED:
                        status = sched.job_status(self.pav_cfg, test)

                    if status != STATES.SCHEDULED:
                        # The test has moved past the scheduled state
                        wait_result = None
                        break

                if wait_result is None:
                    # Sleep at most SLEEP INTERVAL seconds, minus the time
                    # we spent checking our jobs.
                    time.sleep(self.WAIT_INTERVAL - (time.time() - last_time))

        fprint("{} test{} started as test series {}."
               .format(len(all_tests),
                       's' if len(all_tests) > 1 else '', self.sid),
               file=self.outfile,
               color=output.GREEN)

        return 0

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
    def from_id(cls, pav_cfg, sid: str,
                outfile: TextIO = StringIO(), errfile: TextIO = StringIO()):
        """Load a series object from the given id, along with all of its
    associated tests.

    :raises TestSeriesError: From invalid series id or path."""

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
                series_info_files = [SERIES_OUT_FN,
                                     SERIES_PGID_FN,
                                     CONFIG_FN,
                                     DEPENDENCY_FN]
                if path.name not in series_info_files:
                    logger.info("Bad test id in series from dir '%s'", path)
                continue

            try:
                tests.append(TestRun.load(pav_cfg, test_id=test_id))
            except TestRunError as err:
                logger.info("Error loading test %s: %s",
                            test_id, err.args[0])

        return cls(pav_cfg, tests, _id=sid, outfile=outfile, errfile=errfile)

    def load_dep_graph(self):
        """Load a series object from the given id, along with the config and
        dependency tree."""

        try:
            with (self.path/DEPENDENCY_FN).open() as dep_file:
                dep = dep_file.readline()

            with (self.path/CONFIG_FN).open() as config_file:
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
            set_obj = TestSet(self.pav_cfg, set_name, set_info['tests'], modes,
                              self.config['host'], set_info['only_if'],
                              set_info['not_if'], self)
            self.test_sets[set_name] = set_obj

        # create doubly linked graph of TestSet objects
        for set_name in self.dep_graph:
            self.test_sets[set_name].before.update(self.dep_graph[set_name])

            next_list = []
            for s_n in self.dep_graph:
                if set_name in self.dep_graph[s_n]:
                    next_list.append(s_n)
            self.test_sets[set_name].after.update(next_list)

        return

    def cancel_series(self):
        """Goes through all test objects assigned to series and cancels tests
        that haven't been completed. """

        for test_id, test_obj in self.tests.items():
            if not (test_obj.path/'RUN_COMPLETE').exists():
                sched = schedulers.get_plugin(test_obj.scheduler)
                sched.cancel_job(test_obj)
                test_obj.status.set(STATES.COMPLETE, "Killed by SIGTERM.")
                test_obj.set_run_complete()

    def run_series(self):
        """Runs series."""

        # handles SIGTERM (15) signal
        def sigterm_handler(_signals, _frame_type):
            """Calls cancel_series and exists."""

            self.cancel_series()
            sys.exit()

        signal.signal(signal.SIGTERM, sigterm_handler)

        # create set graph once
        self.create_set_graph()

        # run sets in order
        while True:

            all_sets = list(self.test_sets.keys())
            started = []
            waiting = set()
            finished = []

            # kick off any sets that aren't waiting on any sets to complete
            for set_name, set_obj in self.test_sets.items():
                if not set_obj.before:
                    set_obj.run_set()
                    started.append(set_name)
                    waiting = set(all_sets) - set(started)

            while waiting:
                self.series_test_handler(finished, started, waiting)
                time.sleep(0.1)

            self.update_finished_list(finished, started)

            # if restart isn't necessary, break out of loop
            if not str_bool(self.config['restart']):
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

    def update_finished_list(self, finished, started):
        """Updates finished and started lists if necessary. """

        for set_name in started:
            if self.test_sets[set_name].is_done():
                finished.append(set_name)
                started.remove(set_name)

    def series_test_handler(self, finished, started, waiting):
        """Loops through all current sets, calls necessary functions,
        and updates lists as necessary. """

        self.update_finished_list(finished, started)

        # logic on what needs to be done based on new information
        temp_waiting = copy.deepcopy(waiting)
        for set_name in temp_waiting:
            # check if all the sets this set depends on are finished
            ready = all(prev in finished
                        for prev in self.test_sets[set_name].before)
            if ready:
                # this set requires that the sets it depends on passes
                if str_bool(self.config['series'][set_name]['depends_pass']):
                    # all the tests passed, so run this test
                    if self.test_sets[set_name].all_pass:
                        self.test_sets[set_name].run_set()
                        started.append(set_name)
                        waiting.remove(set_name)
                    # the tests didn't all pass, so skip this test
                    else:
                        self.test_sets[set_name].skip_set()
                        finished.append(set_name)
                        waiting.remove(set_name)
                else:
                    # All the sets completed and we don't care if they passed so
                    # run this set
                    self.test_sets[set_name].run_set()
                    started.append(set_name)
                    waiting.remove(set_name)

    @staticmethod
    def get_pgid(pav_cfg, id_):
        """Returns pgid of series if it exists. """

        try:
            id_ = int(id_[1:])
        except ValueError:
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

    @property
    def timestamp(self):
        """Return the unix timestamp for this series, based on the last
modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return self.path.stat().st_mtime
