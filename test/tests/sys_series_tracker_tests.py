import io
import json
import os

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import system_variables
from pavilion import utils
from pavilion.unittest import PavTestCase


class SysNameSeriesTrackerTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_sys_name_tracker(self):
        """Make sure the expected values are stored in the user.json file."""

        user = utils.get_login()

        sys_vars = system_variables.get_vars(True)
        sys_name = sys_vars['sys_name']

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'hello_world'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()
        run_cmd.errfile = run_cmd.outfile
        run_cmd.run(self.pav_cfg, args)

        series = run_cmd.last_series

        json_file = self.pav_cfg.working_dir/'users'
        json_file /= '{}.json'.format(user)

        with json_file.open('r') as json_series_file:
            data = json.load(json_series_file)

        self.assertEqual(data[sys_name], series.sid)
