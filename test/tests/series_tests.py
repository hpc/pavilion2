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

        # check modes
        for name, test_dict in series_man.test_info.items():
            if 'obj' in test_dict.keys():
                for test_obj in test_dict['obj']:
                    vars = test_obj.var_man.variable_sets['var']
                    # check if smode 2 values are there
                    a_num_value = vars.get('another_num', None, None)
                    num1_value = vars.get('num1', None, None)
                    num2_value = vars.get('num2', None, None)
                    self.assertEqual(a_num_value, '13')
                    self.assertEqual(num1_value, '11')
                    self.assertEqual(num2_value, '98')

                    # make sure 'echo_test.a' has both modes applied to it
                    if name == 'echo_test.a':
                        asdf_value = vars.get('asdf', None, None)
                        letters_value = vars.get('letters', None, None)
                        self.assertEqual(asdf_value, 'asdf1')
                        self.assertEqual(letters_value, 'cup')

