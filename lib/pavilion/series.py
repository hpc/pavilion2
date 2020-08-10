"""Series are a collection of test runs."""

import logging
import json
import os
import pathlib
import time
import copy
import codecs
import sys
import errno
import signal
from pathlib import Path

from pavilion import system_variables
from pavilion import utils
from pavilion import commands
from pavilion import schedulers
from pavilion import arguments
from pavilion import test_config
from pavilion import system_variables
from pavilion import output
from pavilion.test_config import resolver
from pavilion.status_file import STATES
from pavilion.builder import MultiBuildTracker
from pavilion.lockfile import LockFile
from pavilion import dir_db
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


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


class SeriesManager:
    """Series Manager"""

    def __init__(self, pav_cfg, series_obj, series_cfg):
        # set everything up

        self.pav_cfg = pav_cfg
        self.series_obj = series_obj
        self.series_cfg = series_cfg

        self.series_section = self.series_cfg['series']

        self.dep_graph = {}  # { test_name: [tests it depends on] }
        self.make_dep_graph()

        universal_modes = self.series_cfg['modes']

        self.test_info = {}

        for test_name, test_config in self.series_section.items():
            self.test_info[test_name] = {}
            test_modes = test_config['modes']
            all_modes = universal_modes + test_modes
            self.test_info[test_name]['modes'] = all_modes
            self.test_info[test_name]['only_if'] = test_config['only_if']
            self.test_info[test_name]['not_if'] = test_config['not_if']

        # create doubly linked graph
        for test_name in self.dep_graph:
            prev_list = self.dep_graph[test_name]
            self.test_info[test_name]['prev'] = prev_list

            next_list = []
            for t_n in self.dep_graph:
                if test_name in self.dep_graph[t_n]:
                    next_list.append(t_n)
            self.test_info[test_name]['next'] = next_list

        return

    def run_series(self):

        # handles SIGTERM (15) signal
        def sigterm_handler(*args):

            for test_name in self.started:
                for test_obj in self.test_info[test_name]['obj']:
                    test_obj.status.set(STATES.COMPLETE,
                                        "Killed by SIGTERM.")
                    test_obj.set_run_complete()

            sys.exit()

        signal.signal(signal.SIGTERM, sigterm_handler)

        # run tests in order
        while True:
            self.all_tests = list(self.test_info.keys())
            self.started = []
            self.finished = []
            self.not_started = []

            # kick off tests that aren't waiting on any tests to complete
            for test_name in self.test_info:
                if not self.test_info[test_name]['prev']:
                    self.run_test(test_name)
                    self.not_started = \
                        list(set(self.all_tests) - set(self.started))

            while len(self.not_started) != 0:
                self.series_tests_handler()
                time.sleep(0.1)

            # if restart isn't necessary, break out of loop
            if self.series_cfg['restart'] not in ['True', 'true']:
                break
            else:
                # wait for all tests to be finished to continue
                done = False
                while not done:
                    done = True
                    for test_name in self.test_info:
                        if not self.is_done(test_name):
                            done = False
                            break
                    time.sleep(0.1)

        return

    def series_tests_handler(self):

        # update lists
        self.check_and_update()

        # logic on what needs to be done based on new information
        temp_waiting = copy.deepcopy(self.not_started)
        for test_name in temp_waiting:
            ready = all(wait in self.finished for wait in self.test_info[
                test_name]['prev'])
            if ready:
                if self.series_section[test_name]['depends_pass'] \
                        in ['True', 'true']:
                    if self.all_tests_passed(
                            self.test_info[test_name]['prev']):
                        # We care that all the tests this test depended
                        # on passed, and they did, so run this test.
                        self.run_test(test_name)
                        self.not_started.remove(test_name)
                    else:
                        # The dependent tests did not pass, and we care.
                        # Skip this test.
                        temp_resolver = resolver.TestConfigResolver(
                            self.pav_cfg)
                        raw_configs = temp_resolver.load_raw_configs(
                            [test_name], [],
                            self.test_info[test_name]['modes']
                        )
                        self.test_info[test_name]['obj'] = []
                        for config in raw_configs:
                            # Delete the conditionals - we're already
                            # skipping this test but for different reasons.
                            del config['only_if']
                            del config['not_if']
                            skipped_test = TestRun(self.pav_cfg, config)
                            skipped_test.status.set(
                                STATES.SKIPPED,
                                "Skipping. Previous test did not PASS.")
                            skipped_test.set_run_complete()
                            self.test_info[test_name]['obj'].append(
                                skipped_test
                            )
                            self.series_obj.add_tests([skipped_test])
                        self.not_started.remove(test_name)
                        self.finished.append(test_name)
                else:
                    # All tests completed, and we don't care if they passed.
                    self.run_test(test_name)
                    self.not_started.remove(test_name)

    def run_test(self, test_name):

        # basically copy what the run command is doing here
        mb_tracker = MultiBuildTracker()

        run_cmd = commands.get_command('run')

        # run.RunCommand._get_tests function
        try:
            new_conditions = {
                'only_if': self.test_info[test_name]['only_if'],
                'not_if': self.test_info[test_name]['not_if']
            }

            # resolve configs
            configs_by_sched = run_cmd.get_test_configs(
                pav_cfg=self.pav_cfg,
                host=None,
                test_files=[],
                tests=[test_name],
                modes=self.test_info[test_name]['modes'],
                overrides=None,
                conditions=new_conditions
            )

            # configs -> tests
            tests_by_sched = run_cmd.configs_to_tests(
                pav_cfg=self.pav_cfg,
                configs_by_sched=configs_by_sched,
                mb_tracker=mb_tracker,
                build_only=False,
                rebuild=False
            )

        except commands.CommandError as err:
            # probably won't happen
            err = codecs.decode(str(err), 'unicode-escape')
            self.finished.append(test_name)
            return None

        except test_config.file_format.TestConfigError as err:
            self.finished.append(test_name)
            return None

        if tests_by_sched is None:
            # probably won't happen but just in case
            self.finished.append(test_name)
            return None

        all_tests = sum(tests_by_sched.values(), [])
        run_cmd.last_tests = list(all_tests)

        if not all_tests:
            # probably won't happen but just in case
            self.test_info[test_name]['obj'] = run_cmd.last_tests
            self.finished.append(test_name)
            return None

        # assign test to series and vice versa
        self.series_obj.add_tests(all_tests)
        run_cmd.last_series = self.series_obj
        self.test_info[test_name]['obj'] = run_cmd.last_tests

        # make sure result parsers are ok
        res = run_cmd.check_result_format(all_tests)
        if res != 0:
            run_cmd.complete_tests(all_tests)
            self.finished.append(test_name)
            return None

        # attempt to build
        res = run_cmd.build_local(
            tests=all_tests,
            max_threads=self.pav_cfg.build_threads,
            mb_tracker=mb_tracker,
            build_verbosity=0
        )
        if res != 0:
            run_cmd.complete_tests(all_tests)
            self.finished.append(test_name)
            return None

        if self.series_cfg['simultaneous'] is None:
            run_cmd.run_tests(
                pav_cfg=self.pav_cfg,
                tests_by_sched=tests_by_sched,
                series=self.series_obj,
                wait=None,
                report_status=False
            )
            self.started.append(test_name)
        else:
            simult = int(self.series_cfg['simultaneous'])

            # [ { sched: test_obj}, { sched: test_obj }, etc. ]
            list_of_tests_by_sched = []
            for sched, test_objs in tests_by_sched.items():
                for test_obj in test_objs:
                    list_of_tests_by_sched.append({sched: [test_obj]})

            self.started.append(test_name)
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

        while len(self.get_currently_running()) >= simul:
            time.sleep(0.1)

        return

    # checks for currently running tests
    def get_currently_running(self):
        cur_run = []
        for test_name in self.started:
            for test_obj in self.test_info[test_name]['obj']:
                temp_state = test_obj.status.current().state
                if temp_state in ['SCHEDULED', 'RUNNING']:
                    cur_run.append(test_obj)
        return cur_run

    # determines if test/s is/are done running
    def is_done(self, test_name):
        if 'obj' not in self.test_info[test_name].keys():
            return False

        test_obj_list = self.test_info[test_name]['obj']
        # test is considered "finished" if:
        # test has 'RUN_COMPLETE' file in test_run dir
        for test_obj in test_obj_list:

            # if scheduler is known, check status and update
            # pylint: disable=protected-access
            if test_obj._job_id:
                test_sched = schedulers.get_plugin(test_obj.scheduler)
                test_sched.job_status(self.pav_cfg, test_obj)

            if not (test_obj.path / 'RUN_COMPLETE').exists():
                return False
        return True

    def all_tests_passed(self, test_names):

        for test_name in test_names:
            if 'obj' not in self.test_info[test_name].keys():
                return False

            test_obj_list = self.test_info[test_name]['obj']
            for test_obj in test_obj_list:
                if test_obj.results['result'] != 'PASS':
                    return False

        return True

    def check_and_update(self):

        temp_started = copy.deepcopy(self.started)
        for test_name in temp_started:
            if self.is_done(test_name):
                self.started.remove(test_name)
                self.finished.append(test_name)

    def make_dep_graph(self):
        # has to be a graph of test sets
        for test_name, test_config in self.series_section.items():
            self.dep_graph[test_name] = test_config['depends_on']


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
            configs_by_sched = run_cmd.get_test_configs(
                pav_cfg=self.pav_cfg,
                host=None,
                test_files=[],
                tests=self.tests,
                modes=self.modes,
                overrides=None,
                conditions=new_conditions
            )

            # configs->tests
            tests_by_sched = run_cmd.configs_to_tests(
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
        res = run_cmd.build_local(
            tests=all_tests,
            max_threads=self.pav_cfg.build_threads,
            mb_tracker=mb_tracker,
            build_verbosity=0
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
        :param dict series_cfg: Series config, if generated from a serie file.
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

        else:
            self._id = _id
            self.path = dir_db.make_id_path(series_path, self._id)

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self._id))

    def get_currently_running(self):
        cur_run = []
        for test_id, test_obj in self.tests.items():
            temp_state = test_obj.status.current().state
            if temp_state in ['SCHEDULED', 'RUNNING']:
                cur_run.append(test_obj)
        return cur_run

    def create_dependency_tree(self):

        # create dependency tree
        for set_name, set_config in self.config['series'].items():
            self.dep_graph[set_name] = set_config['depends_on']

        temp_original_dep = copy.deepcopy(self.dep_graph)

        # check for circular dependencies
        unresolved = list(self.dep_graph.keys())
        resolved = []

        while unresolved:
            resolved_something = False

            for unresolved_set in unresolved:
                # Find if there any dependencies are/were resolved
                temp_dep_list = copy.deepcopy(self.dep_graph[unresolved_set])
                for dep in self.dep_graph[unresolved_set]:
                    if dep in resolved:
                        temp_dep_list.remove(dep)
                self.dep_graph[unresolved_set] = temp_dep_list

                # If this was already fully resolved, add it to resolved
                if not self.dep_graph[unresolved_set]:
                    resolved.append(unresolved_set)
                    unresolved.remove(unresolved_set)
                    resolved_something = True

            if not resolved_something:
                break

        if unresolved:
            raise TestSeriesError(
                "Circular dependencies detected. Please fix. No tests are run.",
            )

        self.dep_graph = temp_original_dep

        return

    @property
    def id(self):  # pylint: disable=invalid-name
        """Return the series id as a string, with an 's' in the front to
differentiate it from test ids."""

        return 's{}'.format(self._id)

    @classmethod
    def from_id(cls, pav_cfg, id_):
        """Load a series object from the given id, along with all of its
associated tests."""

        try:
            id_ = int(id_[1:])
        except TypeError as err:
            pass

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, id_)

        if not series_path.exists():
            raise TestSeriesError("No such series found: '{}' at '{}'"
                                  .format(id_, series_path))

        logger = logging.getLogger(cls.LOGGER_FMT.format(id_))

        tests = []
        for path in os.listdir(str(series_path)):
            link_path = series_path/path
            if link_path.is_symlink() and link_path.is_dir():
                try:
                    test_id = int(link_path.name)
                except ValueError:
                    logger.info(
                        "Bad test id in series from dir '%s'",
                        link_path)
                    continue

                try:
                    tests.append(TestRun.load(pav_cfg, test_id=test_id))
                except TestRunError as err:
                    logger.info(
                        "Error loading test %s: %s",
                        test_id, err
                    )

            else:
                series_info_files = ['series.out', 'series.pgid', 'config',
                                     'dependency']
                if link_path.name not in series_info_files:
                    logger.info("Polluted series directory in series '%s'",
                                series_path)
                    raise ValueError(link_path)

        return cls(pav_cfg, tests, _id=id_)

    @classmethod
    def get_config_dep_from_id(cls, pav_cfg, id_):
        """Load a series object from the given id, along with the config and
        dependency tree."""

        id_ = int(id_)

        series_path = pav_cfg.working_dir/'series'
        series_path = dir_db.make_id_path(series_path, id_)

        try:
            with open(str(series_path/'config'), 'r') as config_file:
                config = config_file.readline()
            config = json.loads(config)

            with open(str(series_path/'dependency'), 'r') as dep_file:
                dep = dep_file.readline()
            dep = json.loads(dep)

        except FileNotFoundError as fnfe:
            raise TestSeriesError("Files not found. {}".format(fnfe))

        return cls(pav_cfg, _id=id_, series_config=config, dep_graph=dep)

    def create_set_graph(self):

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

            # for set_name, set_obj in self.test_sets.items():
            #     set_obj.kill_set()
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
                        if not set_obj.done:
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
                    except json.decoder.JSONDecodeError as err:
                        # File was empty, therefore json couldn't be loaded.
                        pass
                with json_file.open('w') as json_series_file:
                    data[sys_name] = self.id
                    json_series_file.write(json.dumps(data))

            except FileNotFoundError as err:
                # File hadn't been created yet.
                with json_file.open('w') as json_series_file:
                    data[sys_name] = self.id
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
