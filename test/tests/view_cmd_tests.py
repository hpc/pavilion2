"""Exercise the view command."""

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class ViewCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_view(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'view', 'hello_world'
        ])

        view_cmd = commands.get_command(args.command_name)
        view_cmd.silence()

        self.assertEqual(view_cmd.run(self.pav_cfg, args), 0)
