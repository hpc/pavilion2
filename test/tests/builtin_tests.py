from pavilion import commands, plugins, arguments
from pavilion.unittest import PavTestCase


class BuiltinTests(PavTestCase):
    """Test Pavilion builtins."""

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def test_survey_mode_config(self):

        run_cmd = commands.get_command('run')
        #run_cmd.silence()
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            '-m', 'survey',
            'hello_c'
        ])

        ret = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(ret, 0)
