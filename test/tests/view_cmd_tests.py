"""Exercise the view command."""
from pavilion import arguments
from pavilion import commands
from pavilion.unittest import PavTestCase


class ViewCmdTests(PavTestCase):

    def test_view(self):

        view_cmd = commands.get_command('view')
        view_cmd.silence()

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'view', 'hello_world'
        ])

        self.assertEqual(view_cmd.run(self.pav_cfg, args), 0)
