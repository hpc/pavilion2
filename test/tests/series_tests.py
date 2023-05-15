"""Tests for the Series object."""
from collections import OrderedDict

from pavilion import series
from pavilion import series_config
from pavilion.errors import TestSeriesError
from pavilion.unittest import PavTestCase


class SeriesTests(PavTestCase):

    def test_init(self):
        """Check initialization of the series object."""

        # Initialize from scratch
        series1 = series.TestSeries(
            pav_cfg=self.pav_cfg,
            series_cfg=series_config.generate_series_config('test')
        )

        # Add a basic test set and save.
        series1.add_test_set_config('series1', ['pass_fail'])

        series2 = series.TestSeries.load(self.pav_cfg, series1.sid)

        # Make sure a loaded series is the same as the original
        for attr in series1.__dict__.keys():
            self.assertEqual(series1.__getattribute__(attr),
                             series2.__getattribute__(attr), attr)

    def test_set_ordering(self):
        """Verify that the order of entries in series files is kept intact on load."""

        cfg = series_config.load_series_config(self.pav_cfg, 'order')

        series1 = series.TestSeries(self.pav_cfg, cfg)
        series1.add_test_set_config('test3', ['bar'])
        series1._create_test_sets()

        expected_order = ['zazzle', 'blargl', 'foo', 'snit', 'r2d2', 'test3']
        order = list(series1.test_sets.keys())

        self.assertEqual(expected_order, order, "Test sets improperly ordered.")

    def test_series_circle(self):
        """Test if it can detect circular references and that ordered: True
        works as intended."""

        config = series_config.make_config({
            'test_sets': {
                'set1': {
                    },
                'set2': {
                    'depends_on': ['set1', 'set4']
                },
                'set3': {
                    'depends_on': ['set2']
                },
                'set4': {
                    'depends_on': ['set3']
                }
            }})

        series1 = series.TestSeries(self.pav_cfg, config)
        with self.assertRaises(TestSeriesError):
            series1._create_test_sets()

        series_sec_cfg = OrderedDict()
        series_sec_cfg['set1'] = {}
        series_sec_cfg['set2'] = {'depends_on': 'set4'}
        series_sec_cfg['set3'] = {}
        series_sec_cfg['set4'] = {}

        config = series_config.make_config({
            'ordered': True,
            'test_sets': series_sec_cfg,
        })
        series2 = series.TestSeries(self.pav_cfg, config)
        with self.assertRaises(TestSeriesError):
            series2._create_test_sets()

    def test_series_simultaneous(self):
        """Tests to see if simultaneous: <num> works as intended. """
        series_sec_cfg = OrderedDict()
        series_sec_cfg['set1'] = {'tests': ['echo_test.b']}
        series_sec_cfg['set2'] = {'tests': ['echo_test.b']}

        series_cfg = series_config.make_config({
                'test_sets': series_sec_cfg,
                'modes':        ['smode2'],
                'simultaneous': '1',
            })

        test_series_obj = series.TestSeries(self.pav_cfg, series_cfg=series_cfg)
        test_series_obj.run()
        test_series_obj.wait(timeout=10)

        last_ended = None
        for test_id in sorted(test_series_obj.tests):
            test_obj = test_series_obj.tests[test_id]
            started = test_obj.results['started']
            ended = test_obj.results['finished']
            if last_ended is not None:
                self.assertLessEqual(last_ended, started)
            last_ended = ended

    def test_series_modes(self):
        """Test if modes and host are applied correctly."""

        series_cfg = series_config.make_config({
            'test_sets': {
                'only_set': {
                    'modes':      ['smode1'],
                    'tests':      ['echo_test.a']},
            },
            'modes': ['smode2'],
            'host': 'this'
        })

        test_series_obj = series.TestSeries(self.pav_cfg, series_cfg=series_cfg)
        test_series_obj.run()
        test_series_obj.wait(5)

        self.assertNotEqual(test_series_obj.tests, {})

        for test_id, test_obj in test_series_obj.tests.items():
            varsets = test_obj.var_man.variable_sets['var']
            a_num_value = varsets.get('another_num', None, None)
            self.assertEqual(a_num_value, '13')
            asdf_value = varsets.get('asdf', None, None)
            self.assertEqual(asdf_value, 'asdf1')
            hosty_value = varsets.get('hosty', None, None)
            self.assertEqual(hosty_value, 'this')

    def test_series_depends(self):
        """Tests if dependencies work as intended."""

        cfg = series_config.make_config({
                'test_sets': {
                    'a': {},
                    'b': {'depends_on': ['a']},
                    'c': {'depends_on': ['a', 'b']},
                    'd': {'depends_on': ['c', 'b']},
                    'e': {},
                }})

        series1 = series.TestSeries(self.pav_cfg, series_cfg=cfg)
        series1._create_test_sets()

        a = series1.test_sets['a']
        b = series1.test_sets['b']
        c = series1.test_sets['c']
        d = series1.test_sets['d']
        e = series1.test_sets['e']

        self.assertEqual(a.parent_sets, set())
        self.assertEqual(a.child_sets, {b, c})
        self.assertEqual(b.parent_sets, {a})
        self.assertEqual(b.child_sets, {c, d})
        self.assertEqual(c.parent_sets, {a, b})
        self.assertEqual(c.child_sets, {d})
        self.assertEqual(d.parent_sets, {b, c})
        self.assertEqual(d.child_sets, set())
        self.assertEqual(e.parent_sets, set())
        self.assertEqual(e.child_sets, set())

    def test_sched_errors(self):
        """Errors getting scheduler variables are deferred. Make sure we catch them
        appropriately."""

        cfg = series_config.make_config({
            'test_sets': {
                'a': {
                    'tests': ['sched_errors.a_error', 'sched_errors.b_skipped']
                }
            }
        })

        series1 = series.TestSeries(self.pav_cfg, config=cfg)
        with self.assertRaises(TestSeriesError):
            series1.run()

        cfg = series_config.make_config({
            'test_sets': {
                'a': {
                    'tests': ['sched_errors.c_other_error', 'sched_errors.b_skipped']
                }
            }
        })


        series1 = series.TestSeries(self.pav_cfg, config=cfg)
        with self.assertRaises(TestSeriesError):
            series1.run()

    def test_series_conditionals_only_if_ok(self):
        """Test that adding a conditional that always matches produces tests that
        run when expected."""

        test_series_obj = self._setup_conditionals_test(
            only_if={
                # This will always match
                "bob": ["bob"]
            })

        for test_id, test_obj in test_series_obj.tests.items():
            if 'always' in test_obj.name:
                self.assertEqual(test_obj.results['result'], 'PASS')
            else:
                self.assertIsNone(test_obj.results['result'])

    def test_series_conditionals_only_if_nope(self):
        """Check that adding a non-matching only_if causes all tests to skip."""

        test_series_obj = self._setup_conditionals_test(
            only_if={
                # This will always match
                "bob": ["suzy"]
            })

        for test_id, test_obj in test_series_obj.tests.items():
            self.assertIsNone(
                test_obj.results['result'],
                msg = "Test {} should have had a null result.".format(test_obj.name))

    def test_series_conditionals_not_if_ok(self):
        """Check that adding a non-matching not_if causes no change."""

        test_series_obj = self._setup_conditionals_test(
            not_if={
                # This will always match
                "bob": ["suzy"]
            })

        for test_id, test_obj in test_series_obj.tests.items():
            if 'always' in test_obj.name:
                self.assertEqual(test_obj.results['result'], 'PASS')
            else:
                self.assertIsNone(test_obj.results['result'])

    def test_series_conditionals_not_if_nope(self):
        """Check that adding a matching not_if causes all tests to skip."""

        test_series_obj = self._setup_conditionals_test(
            not_if={
                # This will always match
                "bob": ["bob"]
            })

        for test_id, test_obj in test_series_obj.tests.items():
            self.assertIsNone(
                test_obj.results['result'],
                msg="Test {} should have had a null result.".format(test_obj.name))

    def _setup_conditionals_test(self, only_if=None, not_if=None) -> series.TestSeries:
        """Setup everything for the conditionals test, and return the
        completed test series object."""

        series_cfg = series_config.generate_series_config(
            name='test',
            modes=['smode2'],
        )

        series_obj = series.TestSeries(self.pav_cfg, series_cfg=series_cfg)
        series_obj.add_test_set_config(
            name='test',
            test_names=['conditional'],
            modes=['smode1'],
            only_if=only_if,
            not_if=not_if,
        )

        series_obj.run()
        series_obj.wait(timeout=10)

        return series_obj
