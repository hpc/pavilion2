from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class SuitesTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        run_cmd = commands.get_command('run')
        # run_cmd.silence()

    def test_run_from_suite_directory(self):
        """Test that Pavilion can find and run a test from
        suites directory."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'basic_suite_test'
        ])

        run_cmd = commands.get_command(args.command_name)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
