"""Test the various dir_db filters."""

import argparse
import random
import time
from datetime import timedelta, datetime, date
from pathlib import Path

from pavilion import dir_db
from pavilion import filters
from pavilion import schedulers
from pavilion import commands, arguments
from pavilion.series import TestSeries, STATUS_FN, SeriesInfo
from pavilion.status_file import STATES, SERIES_STATES
from pavilion.test_run import TestRun, TestAttributes, test_run_attr_transform
from pavilion.unittest import PavTestCase
from pavilion.status_file import TestStatusFile, SeriesStatusFile
from pavilion.filters import (FilterParseError, validate_int,
    validate_glob, validate_glob_list, validate_str_list, validate_datetime,
    parse_query, parse_duration)

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

    def test_series_filter_name(self):
        """Check the series name filter option"""

        match_sets = [
            [{'name': 'this.test'}, 'name=this'],
            [{'name': 'this.test.perm'}, 'name=*'],
            [{'name': 'this.test'}, 'name=*.*.*'],
            [{'name': 'this.test'}, 'name=*.?est'],
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
            'created': now - timedelta(minutes=1),
            'sys_name': 'this',
            'user': 'bob',
        }

        never_match_series = {
            'complete': False,
            'created': now - timedelta(minutes=5),
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
            'not complete',
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
            'created':  now - timedelta(minutes=1),
            'name':     'mytest.always_match',
            'result':   TestRun.PASS,
            'sys_name': 'this',
            'user':     'bob',
        }

        never_match_test = {
            'complete': False,
            'created':  now - timedelta(minutes=5),
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
            'not complete',
            'failed',
            #'result_error',
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

        t_filter = filters.parse_query("state=RUN_DONE")
        t_filter2 = filters.parse_query("has_state=RUNNING")

        agg1 = test 

        self.assertFalse(t_filter(agg1))

        agg2 = test2

        self.assertTrue(t_filter(agg2))

        self.assertFalse(t_filter2(agg1))
        self.assertTrue(t_filter2(agg2))

    def test_filter_series_states(self):
        """Check series filtering."""

        series = TestSeries(self.pav_cfg, None)
        series.add_test_set_config('test', test_names=['hello_world'])
        dummy = schedulers.get_plugin('dummy')
        series.run()

        agg1 = series.info()

        series = TestSeries(self.pav_cfg, None)
        series.add_test_set_config('test', test_names=['hello_world'])

        agg2 = series.info()

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

    def test_error_on_bad_query(self):
        with self.assertRaises(FilterParseError):
            test_filter = filters.parse_query("garbage")
            
    def test_validators(self):
        
        @validate_int
        def ret_int(_):
            return 42

        @validate_glob
        def ret_str(_):
            return "The quick brown fox"

        @validate_glob_list
        def ret_glob_list(_):
            return ["cat", "car", "cad", "cam"]

        @validate_str_list
        def ret_str_list(_):
            return ["Kings", "play", "chess", "on", "fine", "glass", "sets"]

        @validate_datetime
        def ret_datetime(_):
            return datetime.now()

        self.assertTrue(ret_int(None, "=", "42"))
        self.assertFalse(ret_int(None, "=", "40"))
        self.assertTrue(ret_int(None, ">=", "0"))
        
        with self.assertRaises(FilterParseError):
            ret_int(None, "!", "57")

        with self.assertRaises(FilterParseError):
            ret_int(None, "=", "batman")

        self.assertTrue(ret_str(None, "=", "the Quick brown Fox"))
        self.assertTrue(ret_str(None, "=", "The*"))
        self.assertFalse(ret_str(None, "=", "The hairy yellow sloth"))
        self.assertTrue(ret_str(None, "!=", "The slippery blue whale"))

        with self.assertRaises(FilterParseError):
            ret_str(None, "%", "The quick brown fox")

        self.assertTrue(ret_glob_list(None, "=", "ca?"))
        self.assertFalse(ret_glob_list(None, "=", "cat"))
        self.assertFalse(ret_glob_list(None, "=", "cab"))

        with self.assertRaises(FilterParseError):
            ret_glob_list(None, "&", "*")

        self.assertTrue(ret_str_list(None, "=", "CHESS"))
        self.assertFalse(ret_str_list(None, "=", "parcheesi"))
        
        with self.assertRaises(FilterParseError):
            ret_str_list(None, "💩", "glass") 

        self.assertTrue(ret_datetime(None, ">", "1945-09-06"))
        self.assertFalse(ret_datetime(None, "<", "1945-11-11T11:00"))
        self.assertTrue(ret_datetime(None, ">", "5 minutes"))
        self.assertTrue(ret_datetime(None, ">=", "2seconds"))
        self.assertFalse(ret_datetime(None, "=", "-17weeks"))
        self.assertTrue(ret_datetime(None,  "!=", "0 days"))

        with self.assertRaises(FilterParseError):
            ret_datetime(None, "=", "Long ago in a distant land...")

    def test_filter_errors_on_bad_input(self):
        with self.assertRaises(FilterParseError):
            parse_query("")

        with self.assertRaises(FilterParseError):
            parse_query("sudo rm -rf /")


    def test_filter_boolean_logic(self):
        """Test that the filter's three-valued logic works as expected
        (as specified by Paul). See transformer.py for detailed
        specification."""
        
        test_dict = {
            'name': None,
            'user': 'Batman',
            'created': None,
            'sys_name': 'batcave',
        }

        attrs = test_dict

        # None or None should be None -> False
        ff1 = parse_query("created<1 day or name=foo")
        # None and None should be False
        ff2 = parse_query("created<1 day and name=foo")
        # None and True should be False
        ff3 = parse_query("created<1 day and user=Batman")
        # None or True should be True
        ff4 = parse_query("created<1 day or user=Batman")
        # not None should be None -> False
        ff5 = parse_query("not created<1 day")
        # Boolean logic goes beyond two items in the implementation
        ff6 = parse_query("user=Mr_Freeze or user=Captain_Cold or user=Killer_Frost or user=Batman")
        ff7 = parse_query("user=Batman and sys_name=batcave and name=Puppet_Master")
        ff8 = parse_query("created < 1 year or user=Mr_Freeze or sys_name=batcave")
        ff9 = parse_query("user=Batman and sys_name=batcave and created > 1 year")

        self.assertFalse(ff1(attrs))
        self.assertFalse(ff2(attrs))
        self.assertFalse(ff3(attrs))
        self.assertTrue(ff4(attrs))
        self.assertFalse(ff5(attrs))
        self.assertTrue(ff6(attrs))
        self.assertFalse(ff7(attrs))
        self.assertTrue(ff8(attrs))
        self.assertFalse(ff9(attrs))

    def test_filter_parentheses(self):
        """Test that parentheses are parsed correctly, and that they behave
        as expected."""

        test_dict = {
            'complete': False,
            'all_started': False
        }

        attrs = test_dict

        ff1 = parse_query("not all_started and complete")
        ff2 = parse_query("(complete)")
        ff3 = parse_query("((all_started))")
        ff4 = parse_query("not (complete and all_started)")

        self.assertFalse(ff1(attrs))
        self.assertFalse(ff2(attrs))
        self.assertFalse(ff3(attrs))
        self.assertTrue(ff4(attrs))

        with self.assertRaises(FilterParseError):
            parse_query("(complete")

        with self.assertRaises(FilterParseError):
            parse_query(")complete)")

    def test_filter_large_query(self):
        """Test that the parser doesn't fail for large query strings"""

        test_dict = {}

        q_str = ("name=foo and (sys_name=button or sys_name=bolt) or "
        "(finished < 2024-03-17T18:43:03 and PASSED) and not (FAILED "
        "or COMPLETE or not has_state=MEGALODON and "
        "(sys_name=chicken or started = 1 year))")

        self.assertFalse(parse_query(q_str)(test_dict))

        q_str = " and ".join(["name=foo"]*1000)

        self.assertFalse(parse_query(q_str)(test_dict))

    def test_parse_duration(self):
        """Test that parsing relative durations behaves as expected."""

        now = datetime.now()

        # Check that these are actually implemented at all
        parse_duration('60 Seconds', now)
        parse_duration('4 MINUTES', now)
        parse_duration('127hours', now)
        parse_duration('500 days', now)
        parse_duration('28 weeks', now)
        parse_duration('6 months', now)
        parse_duration('12 years', now)

        self.assertTrue(parse_duration('0 days', now) == now)
        self.assertTrue(parse_duration('0days', now) == now)

        # The parsing grammar (which we're bypassing here) should prevent
        # negative values from being passed, but we'll test it anyways
        self.assertTrue(parse_duration('-0days', now) == now)

        parsed = parse_duration('13 months', now)
        expected = date(year=now.year - 1, month=now.month - 1, day=now.day)
        self.assertTrue(parsed.date() == expected)

        parsed = parse_duration('12 months', now)
        expected = date(year=now.year - 1, month=now.month, day=now.day)
        self.assertTrue(parsed.date() == expected)

        parsed = parse_duration('1 months', now)
        expected = date(year=now.year, month=now.month - 1, day=now.day)
        self.assertTrue(parsed.date() == expected)

    def test_filter_keywords_implemented(self):
        """Test that the various keywords are actually implemented."""

        queries = {'name=foo', 'state=passed', 'user=dsylvete', 'sys_name=nostalgia',
            'has_state=started', 'created=3 weeks', 'finished=3 seconds', 'partition=west',
            'nodes=[1-4]', 'num_nodes=7', 'started=1 day'}

        for query in queries:
            ff = parse_query(query)
            ff({})

    def test_filter_specials_implemented(self):
        "Test that the special values are implemented."""

        specials = {'complete', 'all_started', 'passed', 'failed', 'result_error'}

        for sp in specials:
            ff = parse_query(sp)
            ff({})

    def test_filter_cli(self):
        """Test that the CLI interface for filters is implemented, and that it
        works."""

        list_cmd = commands.get_command('list')
        list_cmd.silence()

        args = arguments.get_parser().parse_args(['list', 'test_runs', '--filter=user=sunstealer and sys_name=nostalgia'])
