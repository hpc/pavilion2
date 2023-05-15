import io
import json

from pavilion import arguments
from pavilion import commands
from pavilion import utils
from pavilion.sys_vars import base_classes
from pavilion.unittest import PavTestCase


class SysNameSeriesTrackerTests(PavTestCase):

    def test_sys_name_tracker(self):
        """Make sure the expected values are stored in the user.json file."""

        user = utils.get_login()

        sys_vars = base_classes.get_vars(True)
        sys_name = sys_vars['sys_name']

        run_cmd = commands.get_command('run')
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'hello_world'
        ])

        run_cmd.outfile = io.StringIO()
        run_cmd.errfile = run_cmd.outfile
        run_cmd.run(self.pav_cfg, args)

        series = run_cmd.last_series

        json_file = self.pav_cfg.working_dir/'users'
        json_file /= '{}.json'.format(user)

        with json_file.open() as json_series_file:
            data = json.load(json_series_file)

        self.assertEqual(data[sys_name], series.sid)
