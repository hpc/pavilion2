import time
import io
from datetime import datetime

import pavilion.series_util
from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import series
from pavilion.unittest import PavTestCase


class SeriesFileTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_series_circle(self):
        """Test if it can detect circular references and that ordered: True
        works as intended."""

        series_cmd = commands.get_command('series')
        arg_parser = arguments.get_parser()
        series_args = arg_parser.parse_args(['series', 'series_circle1'])

        self.assertRaises(pavilion.series_util.TestSeriesError,
                          lambda: series_cmd.run(self.pav_cfg, series_args))

    def test_series_simultaneous(self):
        """Tests to see if simultaneous: <num> works as intended. """

        series_config = {
            'series':
                            {'only_set':
                                 {'modes':      [],
                                  'tests':      ['echo_test.b'],
                                  'only_if':    {},
                                  'depends_on': [],
                                  'not_if':     {}}
                             },
            'modes':        ['smode2'],
            'simultaneous': '1',
            'restart':      False,
            'ordered':      False,
            'host':         None
        }

        test_series_obj = series.TestSeries(self.pav_cfg,
                                            series_config=series_config)

        test_series_obj.create_test_sets()

        test_series_obj.run()

        # make sure test actually ends
        time.sleep(3)

        test_starts = []
        for test_id, test_obj in test_series_obj.tests.items():
            test_starts.append(test_obj.results['started'])

        timediff1 = test_starts[1] - test_starts[0]
        timediff2 = test_starts[2] - test_starts[1]

        self.assertGreaterEqual(timediff1, 0.5)
        self.assertGreaterEqual(timediff2, 0.5)

    def test_series_modes(self):
        """Test if modes and host are applied correctly."""

        series_config = {
            'series':
                            {'only_set':
                                 {'modes':      ['smode1'],
                                  'depends_on': [],
                                  'tests':      ['echo_test.a'],
                                  'only_if':    {},
                                  'not_if':     {}}
                             },
            'modes':        ['smode2'],
            'simultaneous': None,
            'ordered':      False,
            'restart':      False,
            'host':         'this'
        }

        outfile = io.StringIO()

        test_series_obj = series.TestSeries(self.pav_cfg,
                                            series_config=series_config,
                                            outfile=outfile, errfile=outfile)

        test_series_obj.create_test_sets()

        test_series_obj.run()

        # make sure test actually ends
        time.sleep(0.5)

        self.assertNotEqual(test_series_obj.tests, {})

        for test_id, test_obj in test_series_obj.tests.items():
            vars = test_obj.var_man.variable_sets['var']
            a_num_value = vars.get('another_num', None, None)
            self.assertEqual(a_num_value, '13')
            asdf_value = vars.get('asdf', None, None)
            self.assertEqual(asdf_value, 'asdf1')
            hosty_value = vars.get('hosty', None, None)
            self.assertEqual(hosty_value, 'this')

    def test_series_depends(self):
        """Tests if dependencies work as intended."""

        series_config = {
            'series':
                            {'set_d':
                                 {'modes':        [],
                                  'tests':        ['echo_test.d'],
                                  'depends_on':   ['set_c'],
                                  'depends_pass': 'True',
                                  'only_if':      {},
                                  'not_if':       {}},
                             'set_c':
                                 {'modes':      [],
                                  'tests':      ['echo_test.c'],
                                  'depends_on': [],
                                  'only_if':    {},
                                  'not_if':     {}
                                  }
                             },
            'modes':        ['smode2'],
            'simultaneous': None,
            'ordered':      False,
            'restart':      False,
            'host':         None
        }

        outfile = io.StringIO()
        test_series_obj = series.TestSeries(self.pav_cfg,
                                            series_config=series_config,
                                            outfile=outfile, errfile=outfile)

        test_series_obj.create_dependency_graph()

        test_series_obj.create_test_sets()

        test_series_obj.run()

        time.sleep(0.1)

        # check if echo_test.d is skipped
        for test_id, test_obj in test_series_obj.tests.items():
            if test_obj.name == 'echo_test.d':
                self.assertTrue(test_obj.skipped)

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

        only_if = only_if or {}
        not_if = not_if or {}

        series_config = {
            'series':
                {'only_set':
                    {'modes':      ['smode1'],
                     'depends_on': [],
                     'tests':      [
                         'conditional'
                     ],
                     'only_if':    only_if,
                     'not_if':     not_if}
                 },
            'modes':        ['smode2'],
            'simultaneous': None,
            'ordered':      False,
            'restart':      False,
            'host':         None
        }

        outfile = io.StringIO()

        test_series_obj = series.TestSeries(
            self.pav_cfg, series_config=series_config,
            outfile=outfile, errfile=outfile)

        test_series_obj.create_test_sets()
        test_series_obj.run()
        test_series_obj.wait(timeout=3)

        return test_series_obj
