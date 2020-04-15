"""Series are a collection of test runs."""

import logging
import os

from pavilion import utils
from pavilion import commands
from pavilion import arguments
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError

from pavilion.output import dbg_print  # TODO: delete this


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

    def __init__(self, _pav_cfg, _series_obj, _series_cfg):
        self.pav_cfg = _pav_cfg
        self.series_obj = _series_obj
        self.series_cfg = _series_cfg

        self.sets = self.series_cfg['series']

        self.dep_graph = {}  # { set_name: [set_names it depends on] }
        self.make_dep_graph()

        sets_args = {}
        universal_modes = self.series_cfg['modes']
        # set up sets_args dict
        for set_name, set_info in self.sets.items():

            set_modes = set_info['modes']
            all_modes = universal_modes + set_modes

            args_list = ['run', '--series-id={}'.format(self.series_obj.id)]
            for mode in all_modes:
                args_list.append('-m{}'.format(mode))
            args_list.extend(set_info['test_names'])

            sets_args[set_name] = args_list

        # create TestSet obj for each set
        self.test_sets = {}
        for set_name in sets_args:
            self.test_sets[set_name] = TestSet(
                self.pav_cfg, set_name, sets_args[set_name],
                [], []
            )

        # create doubly linked graph
        for set_name in self.dep_graph:
            prev_str_list = self.dep_graph[set_name]
            for prev in prev_str_list:
                self.test_sets[set_name].add_prev(self.test_sets[prev])

            next_str_list = []
            for s_n in self.dep_graph:
                if set_name in self.dep_graph[s_n]:
                    next_str_list.append(s_n)

            for next in next_str_list:
                self.test_sets[set_name].add_next(self.test_sets[next])

        self.print_stats()

        # kick off tests that aren't waiting on anyone
        for set_name in self.test_sets:
            if not self.test_sets[set_name].get_prev():
                self.test_sets[set_name].run_set()

        self.print_stats()

    def make_dep_graph(self):
        # has to be a graph of test sets
        for set_name in self.sets:
            self.dep_graph[set_name] = self.sets[set_name]['depends_on']

        dbg_print(self.dep_graph, '\n')

    def print_stats(self):
        # dbg_print stats of sets
        for set_name in self.test_sets:
            ts = self.test_sets[set_name]
            dbg_print(ts, ': ', ts.get_stat())


class TestSet:

    # statuses:
    # NO_STAT, NEXT, DID_NOT_RUN, RUNNING, PASS, FAIL

    def __init__(self, _pav_cfg, _name, _args_list,
                 _prev_set, _next_set):

        self.name = _name
        self.pav_cfg = _pav_cfg
        self.args_list = _args_list
        self.prev_set = _prev_set  # has to be a list of TestSet objects
        self.next_set = _next_set  # has to be a list of TestSet objects
        self.status = 'NO_STAT'
        self.test_runs = list()

    def run_set(self):
        run_cmd = commands.get_command('run')
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args(self.args_list)
        run_cmd.run(self.pav_cfg, args)
        dbg_print(run_cmd.last_tests)

        # change statuses
        self.change_stat('RUNNING')
        for n_set in self.next_set:
            if n_set.get_stat() == 'NO_STAT':
                n_set.change_stat('NEXT')

    def change_stat(self, new_stat):
        self.status = new_stat

    def get_stat(self):
        return self.status

    def add_prev(self, prev):
        self.prev_set.append(prev)

    def add_next(self, next):
        self.next_set.append(next)

    def get_prev(self):
        return self.prev_set

    def get_next(self):
        return self.next_set

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


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
