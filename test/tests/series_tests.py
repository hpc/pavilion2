import time
from datetime import datetime

from pavilion.unittest import PavTestCase
from pavilion import commands
from pavilion import arguments
from pavilion import output
from pavilion import plugins
from pavilion import series


class SeriesFileTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_series_file(self):
        """Test if series works as intended."""

        series_cmd = commands.get_command('_series')
        arg_parser = arguments.get_parser()
        series_args = arg_parser.parse_args(['_series', 'series_test'])

        # makes series manager and runs
        series_man = series_cmd.make_series_man(self.pav_cfg, series_args)

        # buffer time, in case last test doesn't finish before returning
        time.sleep(1)

        # check modes
        for name, test_dict in series_man.test_info.items():
            self.assertIn('obj', test_dict.keys())
            for test_obj in test_dict['obj']:
                try:
                    # check modes
                    vars = test_obj.var_man.variable_sets['var']
                    # check if smode 2 values are there
                    a_num_value = vars.get('another_num', None, None)
                    num1_value = vars.get('num1', None, None)
                    num2_value = vars.get('num2', None, None)
                    self.assertEqual(a_num_value, '13')
                    self.assertEqual(num1_value, '11')
                    self.assertEqual(num2_value, '98')
                except KeyError:
                    # none of the above will apply for skipped test
                    if name == 'echo_test.d':
                        pass

        # make sure 'echo_test.a' has both modes applied to it
        for test_obj in series_man.test_info['echo_test.a']['obj']:
            vars = test_obj.var_man.variable_sets['var']
            asdf_value = vars.get('asdf', None, None)
            letters_value = vars.get('letters', None, None)
            self.assertEqual(asdf_value, 'asdf1')
            self.assertEqual(letters_value, 'cup')

        # simultaneous works if second permutation of test b starts at least
        # a whole second after the previous one
        test_b0 = series_man.test_info['echo_test.b']['obj'][0]
        test_b1 = series_man.test_info['echo_test.b']['obj'][1]
        test_b0_start = datetime.strptime(test_b0.results['started'],
                                          '%Y-%m-%d %H:%M:%S.%f')
        test_b1_start = datetime.strptime(test_b1.results['started'],
                                          '%Y-%m-%d %H:%M:%S.%f')
        total_time = (test_b1_start - test_b0_start).total_seconds()
        self.assertGreaterEqual(total_time, 1)

        # depends_pass and depends_on works if test d is SKIPPED
        test_d = series_man.test_info['echo_test.d']['obj'][0]
        self.assertEqual(test_d.status.current().state, 'SKIPPED')

        # only_if works if test wrong_year is skipped (result is None)
        test_wrongyear = series_man.test_info['echo_test.wrong_year']['obj'][0]
        self.assertIsNone(test_wrongyear.results['result'])


