"""Series are a collection of test runs."""

import logging
import os
import pathlib
import time
import copy
import codecs
import sys
import errno
import signal

from pavilion import utils
from pavilion import commands
from pavilion import schedulers
from pavilion import arguments
from pavilion import test_config
from pavilion import system_variables
from pavilion.test_config import resolver
from pavilion.status_file import STATES
from pavilion.builder import MultiBuildTracker
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
    """Series Manger"""

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
                time.sleep(1)

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
                    time.sleep(1)

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
            time.sleep(5)

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


class TestSeries:
    """Series are a collection of tests. Every time """

    LOGGER_FMT = 'series({})'

    def __init__(self, pav_cfg, tests=None, _id=None):
        """Initialize the series.

        :param pav_cfg: The pavilion configuration object.
        :param list tests: The list of test objects that belong to this series.
        :param int _id: The test id number. If this is given, it implies that
            we're regenerating this series from saved files.
        """

        self.pav_cfg = pav_cfg
        self.tests = {}

        if tests:
            self.tests = {test.id: test for test in tests}

        series_path = self.pav_cfg.working_dir/'series'

        # We're creating this series from scratch.
        if _id is None:
            # Get the series id and path.
            try:
                self._id, self.path = TestRun.create_id_dir(series_path)
            except (OSError, TimeoutError) as err:
                raise TestSeriesError(
                    "Could not get id or series directory in '{}': {}"
                    .format(series_path, err))

            if tests:
                # Create a soft link to the test directory of each test in the
                # series.
                for test in tests:
                    link_path = utils.make_id_path(self.path, test.id)

                    try:
                        link_path.symlink_to(test.path)
                    except OSError as err:
                        raise TestSeriesError(
                            "Could not link test '{}' in series at '{}': {}"
                            .format(test.path, link_path, err))

            self._save_series_id()

        else:
            self._id = _id
            self.path = utils.make_id_path(series_path, self._id)

        self._logger = logging.getLogger(self.LOGGER_FMT.format(self._id))

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
        series_path = utils.make_id_path(series_path, id_)

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
                logger.info("Polluted series directory in series '%s'",
                            series_path)
                raise ValueError(link_path)

        return cls(pav_cfg, tests, _id=id_)

    def add_tests(self, test_objs):
        """
        Adds tests to existing series.
        :param test_objs: List of test objects
        :return: None
        """

        for test in test_objs:
            self.tests[test.id] = test

            # attempt to make symlink
            link_path = utils.make_id_path(self.path, test.id)

            try:
                link_path.symlink_to(test.path)
            except OSError as err:
                raise TestSeriesError(
                    "Could not link test '{}' in series at '{}': {}"
                    .format(test.path, link_path, err))

    def _save_series_id(self):
        """Save the series id to the user's .pavilion directory."""

        # Save the last series we created to the .pavilion directory
        # in the user's home dir. Pavilion commands can use this so the
        # user doesn't actually have to know the series_id of tests.

        last_series_fn = self.pav_cfg.working_dir/'users'
        last_series_fn /= '{}.series'.format(utils.get_login())
        try:
            with last_series_fn.open('w') as last_series_file:
                last_series_file.write(self.id)
        except (IOError, OSError):
            # It's ok if we can't write this file.
            self._logger.warning("Could not save series id to '%s'",
                                 last_series_fn)

    @classmethod
    def load_user_series_id(cls, pav_cfg):
        """Load the last series id used by the current user."""
        logger = logging.getLogger(cls.LOGGER_FMT.format('<unknown>'))

        last_series_fn = pav_cfg.working_dir/'users'
        last_series_fn /= '{}.series'.format(utils.get_login())

        if not last_series_fn.exists():
            return None
        try:
            with last_series_fn.open() as last_series_file:
                return last_series_file.read().strip()
        except (IOError, OSError) as err:
            logger.warning("Failed to read series id file '%s': %s",
                           last_series_fn, err)
            return None

    @property
    def timestamp(self):
        """Return the unix timestamp for this series, based on the last
modified date for the test directory."""
        # Leave it up to the caller to deal with time properly.
        return self.path.stat().st_mtime
