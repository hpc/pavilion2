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

        series_man = series_cmd.make_series_man(self.pav_cfg, series_args)

