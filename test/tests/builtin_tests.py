from pavilion import arguments, commands, plugins
from pavilion.status_file import STATES
from pavilion.unittest import PavTestCase


class BuiltinTests(PavTestCase):
    """Test Pavilion builtins."""

    def set_up(self):
        plugins.initialize_plugins(self.pav_cfg)
        build_cmd = commands.get_command('build')
        build_cmd.silence()

    def test_survey(self):
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'build',
            '-H', 'this',
            '-m',
            'survey'
        ])

        build_cmd = commands.get_command(args.command_name)
        build_ret = build_cmd.run(self.pav_cfg, args)
        self.assertEqual(build_ret, 0, msg=build_cmd.outfile.read())
