"""Test the various dir_db filters."""

import argparse
import random
import time
from datetime import timedelta
from pathlib import Path

from pavilion import dir_db
from pavilion import filters
from pavilion import plugins
from pavilion.test_run import TestAttributes, TestRun, test_run_attr_transform
from pavilion.unittest import PavTestCase


class FiltersTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_run_parser_args(self):
        """Test adding standardized test run filter args."""

        class ExitError(RuntimeError):
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

        now = time.time()

        parser = NoExitParser()
        filters.add_test_filter_args(
            parser,
            default_overrides={
                'newer_than': now,
                'name': 'foo.*',
            },
            sort_functions={
                'sort_foo': lambda d: 'foo',
                'sort_bar': lambda d: 'bar',
            }
        )

        with self.assertRaises(ExitError):
            parser.parse_args(['--sort-by=name'])

        args = parser.parse_args([
            '--passed',
            '--complete',
            '--newer-than=',  # Clearing a default.
            '--older-than=1 week',
            '--sort-by=-sort_foo',
        ])

        self.assertTrue(args.passed)
        self.assertTrue(args.complete)
        self.assertIsNone(args.newer_than)
        # Really we're just testing for a datetime.
        self.assertLess(args.older_than,
                        now - timedelta(days=6).total_seconds())
        self.assertEqual(args.sort_by, '-sort_foo')

        common_parser = NoExitParser()
        series_parser = NoExitParser()
        sort_opts = list(filters.SORT_KEYS["SERIES"])

        filters.add_common_filter_args("", common_parser,
                                       filters.SERIES_FILTER_DEFAULTS,
                                       sort_options=sort_opts)
        filters.add_series_filter_args(series_parser)

        self.assertEqual(
            vars(common_parser.parse_args([])),
            vars(series_parser.parse_args([])),
            msg="The series and common args should be the same. If "
                "they've diverged, add tests to check the untested "
                "values (the common ones are tested via the test_run args).")

    def test_make_series_filter(self):
        """Check the filter maker function."""

        now = time.time()

        base = {
            'complete': False,
            'incomplete': False,
            'user': None,
            'sys_name': None,
            'older_than': None,
            'newer_than': None,
        }

        always_match_series = {
            'complete': True,
            'created': now - 5*60,
            'sys_name': 'this',
            'user': 'bob',
        }

        never_match_series = {
            'complete': False,
            'created': now - 1*60,
            'sys_name': 'that',
            'user': 'gary',
        }

        # Setting any of this will be ok for the 'always' pass test,
        # but never ok for the 'never' pass test.
        opt_set = {
            'complete': True,
            'user': 'bob',
            'sys_name': 'this',
            'older_than': now - 2*60,
        }

        # These are the opposite. The 'always' pass test won't, and the
        # 'never' pass will.
        inv_opt_set = {
            'incomplete': True,
            'newer_than': now - 2*60,
        }

        for opt, val in opt_set.items():
            opts = base.copy()
            opts[opt] = val

            series_filter = filters.make_series_filter(**opts)

            self.assertTrue(series_filter(always_match_series),
                            msg="Failed on opt, val ({}, {})"
                            .format(opt, val))
            self.assertFalse(series_filter(never_match_series),
                             msg="Failed on opt, val ({}, {})"
                             .format(opt, val))

        for opt, val in inv_opt_set.items():
            opts = base.copy()
            opts[opt] = val
            series_filter = filters.make_test_run_filter(**opts)

            self.assertFalse(series_filter(always_match_series),
                             msg="Failed on opt, val ({}, {})"
                             .format(opt, val))
            self.assertTrue(series_filter(never_match_series),
                            msg="Failed on opt, val ({}, {})"
                            .format(opt, val))

    def test_make_test_run_filter(self):
        """Check that the series filter options all work."""

        now = time.time()

        always_match_test = {
            'complete': True,
            'created':  now - timedelta(minutes=5).total_seconds(),
            'name':     'mytest.always_match',
            'result':   TestRun.PASS,
            'skipped':  False,
            'sys_name': 'this',
            'user':     'bob',
        }

        never_match_test = {
            'complete': False,
            'created':  now - timedelta(minutes=1).total_seconds(),
            'name':     'yourtest.never_match',
            'result':   TestRun.FAIL,
            'skipped':  True,
            'sys_name': 'that',
            'user':     'dave',
        }

        # Setting any of this will be ok for the 'always' pass test,
        # but never ok for the 'never' pass test.
        opt_set = {
            'show_skipped': 'no',
            'complete':     True,
            'user':         'bob',
            'sys_name':     'this',
            'passed':       True,
            'older_than':   now - timedelta(minutes=2).total_seconds(),
            'name':         'mytest.*',
        }

        # These are the opposite. The 'always' pass test won't, and the
        # 'never' pass will.
        inv_opt_set = {
            'incomplete':   True,
            'failed':       True,
            'result_error': True,
            'newer_than':   now - timedelta(minutes=2).total_seconds(),
        }

        for opt, val in opt_set.items():
            tr_filter = filters.make_test_run_filter(**{opt: val})

            self.assertTrue(tr_filter(always_match_test),
                            msg="Failed on opt, val ({}, {})\n{}"
                            .format(opt, val, always_match_test))
            self.assertFalse(tr_filter(never_match_test),
                             msg="Failed on opt, val ({}, {})\n{}"
                             .format(opt, val, never_match_test))

        for opt, val in inv_opt_set.items():
            tr_filter = filters.make_test_run_filter(**{opt: val})

            self.assertFalse(tr_filter(always_match_test),
                             msg="Failed on opt, val ({}, {})\n{}"
                             .format(opt, val, always_match_test))
            if opt != 'result_error':  # Fails on this one (expected)
                self.assertTrue(
                    tr_filter(never_match_test),
                    msg="Failed on opt, val ({}, {})\n{}"
                        .format(opt, val, never_match_test))

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
            paths=paths,
            transform=test_run_attr_transform,
            order_func=sort, order_asc=ascending).data
        self.assertEqual([t['id'] for t in sorted_tests], ids)

        # And descending.
        sort, ascending = filters.get_sort_opts('-id', "TEST")
        self.assertFalse(ascending)
        sorted_tests = dir_db.select_from(
            paths=paths,
            transform=test_run_attr_transform,
            order_func=sort, order_asc=ascending).data
        self.assertEqual([t['id'] for t in sorted_tests], list(reversed(ids)))
