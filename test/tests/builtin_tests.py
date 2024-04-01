from pavilion import commands, plugins, arguments
from pavilion.unittest import PavTestCase


class BuiltinTests(PavTestCase):
    """Test Pavilion builtins."""

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)        
        run_cmd = commands.get_command("run")
        run_cmd.silence()

    def test_survey_mode_config(self):
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            '-m', 'survey',
            'hello_world_c'
        ])

        run_cmd = commands.get_command(args.command_name)
        ret = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(ret, 0)
