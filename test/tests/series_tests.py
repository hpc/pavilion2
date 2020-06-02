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

        output.fprint("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", color=output.MAGENTA)

        series_cmd = commands.get_command('_series')
        arg_parser = arguments.get_parser()
        series_args = arg_parser.parse_args(['_series', 'series_test'])

        series_man = series_cmd.make_series_man(self.pav_cfg, series_args)
        output.dbg_print(series_man.test_info, color=output.RED)
        # for test_name, info in series_man.test_info.items():
        #     for test in info['obj']:
        #         output.dbg_print(test.results['result'], '\n')

        output.fprint("~~~~~~~~~~~~~~~~~~~~~~~~~~~~~", color=output.MAGENTA)
