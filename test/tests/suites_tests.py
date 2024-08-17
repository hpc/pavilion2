from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class SuitesTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        run_cmd = commands.get_command('run')
        # run_cmd.silence()

    def test_suite_run_from_suite_directory(self):
        """Test that Pavilion can find and run a test from
        a named suites directory."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'basic_suite_test'
        ])

        run_cmd = commands.get_command(args.command_name)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

    def test_suite_run_from_bare_yaml(self):
        """Test that Pavilion can find and run a test from
        a bare yaml file in the suites directory."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'bare_yaml'
        ])

        run_cmd = commands.get_command(args.command_name)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

    def test_suites_host_config(self):
        """Test that Pavilion loads host configs from the
        suites directory"""

        self.assertTrue(False)

    def test_suites_mode_config(self):
        """Test that Pavilion loads mode configs from the
        suites directory"""

        self.assertTrue(False)

    def test_suites_os_config(self):
        """Test that Pavilion loads OS configs from the
        suites directory"""

        self.assertTrue(False)

    def test_suites_build_hash(self):
        """Test that Pavilion ignores config files in the
        suites directory when computing the build hash."""

        self.assertTrue(False)
