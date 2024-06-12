"""Test the various dir_db filters."""

import argparse
import random
import time
from datetime import timedelta, datetime
from pathlib import Path

from pavilion import dir_db
from pavilion import filters
from pavilion import schedulers
from pavilion.series import TestSeries, STATUS_FN, SeriesInfo
from pavilion.status_file import STATES, SERIES_STATES
from pavilion.test_run import TestRun, TestAttributes, test_run_attr_transform
from pavilion.unittest import PavTestCase
from pavilion.status_file import TestStatusFile, SeriesStatusFile
from pavilion.filters import FilterAggregator, TargetType

class FiltersTest(PavTestCase):

    def test_run_parser_args(self):
        """Test adding standardized test run filter args."""

        class ExitError(RuntimeError):
            """Get around auto-exiting when argparse errors happen."""
            pass

        class NoExitParser(argparse.ArgumentParser):
            """Don't exit on failure."""

            def error(self, message):
                """Don't exit on error."""
                raise ExitError()

            def exit(self, status=0, message=None):
                """Don't exit completely on failure."""
                raise ExitError()

        # You can't override a non-existent field.
        with self.assertRaises(RuntimeError):
            filters.add_test_filter_args(
                arg_parser=NoExitParser(),
                default_overrides={'doesnt_exist': True})

        basic = NoExitParser()
        filters.add_test_filter_args(basic)
        args = basic.parse_args(args=[])
        defaults = set(filters.TEST_FILTER_DEFAULTS.keys())
        for key, value in vars(args).items():
            self.assertIn(key, defaults,
                          msg="Missing default for '{}' argument.".format(key))
            self.assertEqual(value, filters.TEST_FILTER_DEFAULTS[key],
                             msg="Misapplied default for '{}' argument."
                                 .format(key))
            defaults.remove(key)
        self.assertEqual(set(), defaults,
                         msg="TEST_FILTER_DEFAULTS has unused keys '{}'"
                             .format(defaults))

        common_parser = NoExitParser()
        series_parser = NoExitParser()
        sort_opts = list(filters.SORT_KEYS["SERIES"])

        filters.add_series_filter_args(series_parser)

        print(vars(series_parser.parse_args([])))

        self.assertEqual(
            vars(common_parser.parse_args([])),
            vars(series_parser.parse_args([])),
            msg="The series and common args should be the same. If "
                "they've diverged, add tests to check the untested "
                "values (the common ones are tested via the test_run args).")

    def test_series_filter_name(self):
        """Check the series name filter option"""

        match_sets = [
            [{'name': 'this.test'}, 'name=this'],
            [{'name': 'this.test.perm'}, 'name=*'],
            [{'name': 'this.test'}, 'name=*.*.*'],
            [{'name': 'this.test'}, 'name=*.?est'],
            [{'name': 'this'}, '']
        ]

        never_match_sets = [
            [{'name': 'this'}, 'name=that'],
            [{'name': 'not.this.test'}, 'name=not.this.again'],
            [{'name': 'this.that'}, 'name=that']
        ]

        for opt in match_sets:
            series_filter = filters.parse_query(opt[1])

            self.assertTrue(series_filter(opt[0]),
                            msg="Failed on opt ({})"
                            .format(opt[1]))

        for opt in never_match_sets:
            series_filter = filters.parse_query(opt[1])

            self.assertFalse(series_filter(opt[0]),
                            msg="Failed on opt ({})"
                            .format(opt[1]))

    def test_test_run_filter_name(self):
        """Check the test run name filter option"""

        match_sets = [
            [{'name': 'this.test'}, 'name=this'],
            [{'name': 'this.test.perm'}, 'name=*'],
            [{'name': 'this.test'}, 'name=*.*.*'],
            [{'name': 'this.test'}, 'name=*.?est'],
            [{'name': 'this'}, '']
        ]

        never_match_sets = [
            [{'name': 'this'}, 'name=that'],
            [{'name': 'not.this.test'}, 'name=not.this.again'],
            [{'name': 'this.that'}, 'name=that']
        ]

        for opt in match_sets:
            test_run_filter = filters.parse_query(opt[1])

            self.assertTrue(test_run_filter(opt[0]),
                            msg="Failed on opt ({})"
                            .format(opt[1]))

        for opt in never_match_sets:
            test_run_filter = filters.parse_query(opt[1])

            self.assertFalse(test_run_filter(opt[0]),
                            msg="Failed on opt ({})"
                            .format(opt[1]))

    def test_make_series_filter(self):
        """Check the filter maker function."""

        now = datetime.now()

        always_match_series = {
            'complete': True,
            'created': now.timestamp() - 5*60,
            'sys_name': 'this',
            'user': 'bob',
        }

        never_match_series = {
            'complete': False,
            'created': now.timestamp() - 1*60,
            'sys_name': 'that',
            'user': 'gary',
        }

        # Setting any of this will be ok for the 'always' pass test,
        # but never ok for the 'never' pass test.
        opt_set = [
            'complete',
            'user=bob',
            'sys_name=this',
            'created>{}'.format((now - timedelta(minutes=2)).isoformat()),
        ]

        # These are the opposite. The 'always' pass test won't, and the
        # 'never' pass will.
        inv_opt_set = [
            '!complete',
            'created<{}'.format((now - timedelta(minutes=2)).isoformat()),
        ]

        for opt in opt_set:
            series_filter = filters.parse_query(opt)

            self.assertTrue(series_filter(always_match_series),
                            msg="Failed on opt ({})"
                            .format(opt))
            self.assertFalse(series_filter(never_match_series),
                             msg="Failed on opt ({})"
                             .format(opt))

        for opt in inv_opt_set:
            series_filter = filters.parse_query(opt)

            self.assertFalse(series_filter(always_match_series),
                            msg="Failed on opt ({})"
                            .format(opt))
            self.assertTrue(series_filter(never_match_series),
                             msg="Failed on opt ({})"
                             .format(opt))

    def test_make_test_run_filter(self):
        """Check that the series filter options all work."""

        now = datetime.now()

        always_match_test = {
            'complete': True,
            'created':  now.timestamp() - timedelta(minutes=5).total_seconds(),
            'name':     'mytest.always_match',
            'result':   TestRun.PASS,
            'sys_name': 'this',
            'user':     'bob',
        }

        never_match_test = {
            'complete': False,
            'created':  now.timestamp() - timedelta(minutes=1).total_seconds(),
            'name':     'yourtest.never_match',
            'result':   TestRun.FAIL,
            'sys_name': 'that',
            'user':     'dave',
        }

        # Setting any of this will be ok for the 'always' pass test,
        # but never ok for the 'never' pass test.
        opt_set = [
            'complete',
            'user=bob',
            'sys_name=this',
            'passed',
            'created>{}'.format((now - timedelta(minutes=2)).isoformat()),
            'name=mytest.*'
        ]

        # These are the opposite. The 'always' pass test won't, and the
        # 'never' pass will.
        inv_opt_set = [
            '!complete',
            'failed',
            'result_error',
            'created<{}'.format((now - timedelta(minutes=2)).isoformat())
        ]

        for opt in opt_set:
            tr_filter = filters.parse_query(opt)

            self.assertTrue(tr_filter(always_match_test),
                            msg="Failed on opt ({})\n{}"
                            .format(opt, always_match_test))
            self.assertFalse(tr_filter(never_match_test),
                             msg="Failed on opt ({})\n{}"
                             .format(opt, never_match_test))

        for opt in inv_opt_set:
            tr_filter = filters.parse_query(opt)

            self.assertFalse(tr_filter(always_match_test),
                             msg="Failed on opt ({})\n{}"
                             .format(opt, always_match_test))
            if opt != 'result_error':  # Fails on this one (expected)
                self.assertTrue(
                    tr_filter(never_match_test),
                    msg="Failed on opt ({})\n{}"
                        .format(opt, never_match_test))

    def test_filter_states(self):
        """Check filtering by test state. These filters require an actual test to
        exist, so are checked separately."""

        test = self._quick_test()
        test2 = self._quick_test()
        test2.run()

        t_filter = filters.parse_query("state==RUN_DONE")

        info = SeriesInfo(test._pav_cfg, test.path) # Is this kosher?
        status_file = TestStatusFile(test.path)
        agg1 = FilterAggregator(test, info, status_file, TargetType.TEST).aggregate()

        self.assertFalse(t_filter(agg1))

        info = SeriesInfo(test._pav_cfg, test2.path)
        status_file = TestStatusFile(test2.path)
        agg2 = FilterAggregator(test2, info, status_file, TargetType.TEST).aggregate()

        self.assertTrue(t_filter(agg2))

        t_filter2 = filters.parse_query("has_state=RUNNING")
        self.assertFalse(t_filter2(agg1))
        self.assertTrue(t_filter2(agg2))

    def test_filter_series_states(self):
        """Check series filtering."""

        series = TestSeries(self.pav_cfg, None)
        series.add_test_set_config('test', test_names=['hello_world'])
        dummy = schedulers.get_plugin('dummy')
        series.run()

        series_info = series.info().attr_dict()
        path = Path(series_info.get('path'))
        test_attrs = TestAttributes(path)
        status_file = SeriesStatusFile(path / STATUS_FN)

        agg1 = FilterAggregator(test_attrs, series_info, status_file, TargetType.SERIES).aggregate()

        series = TestSeries(self.pav_cfg, None)
        series.add_test_set_config('test', test_names=['hello_world'])

        series_info = series.info().attr_dict()
        path = Path(series_info.get('path'))
        test_attrs = TestAttributes(path)
        status_file = SeriesStatusFile(path)

        agg2 = FilterAggregator(test_attrs, series_info, status_file, TargetType.SERIES).aggregate()

        state_filter = filters.parse_query("ALL_STARTED")
        has_state_filter = filters.parse_query("has_state=SET_MAKE")

        self.assertTrue(state_filter(agg1))
        self.assertFalse(state_filter(agg2))

        self.assertTrue(has_state_filter(agg1))
        self.assertFalse(has_state_filter(agg2))

    def test_get_sort_opts(self):
        """Check the sort operation manager."""

        tests = []
        for i in range(20):
            test = self._quick_test()
            tests.append(test)

        ids = [test.id for test in tests]
        ids.sort()

        random.shuffle(tests)
        paths = [test.path for test in tests]

        # Check sorting in ascending direction
        sort, ascending = filters.get_sort_opts('id', "TEST")
        self.assertTrue(ascending)
        sorted_tests = dir_db.select_from(
            self.pav_cfg,
            paths=paths,
            transform=test_run_attr_transform,
            order_func=sort, order_asc=ascending).data
        self.assertEqual([t['id'] for t in sorted_tests], ids)

        # And descending.
        sort, ascending = filters.get_sort_opts('-id', "TEST")
        self.assertFalse(ascending)
        sorted_tests = dir_db.select_from(
            self.pav_cfg,
            paths=paths,
            transform=test_run_attr_transform,
            order_func=sort, order_asc=ascending).data
        self.assertEqual([t['id'] for t in sorted_tests], list(reversed(ids)))
