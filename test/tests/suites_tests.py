from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class SuitesTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        run_cmd = commands.get_command('run')
        build_cmd = commands.get_command('build')
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

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'host1',
            'hosts_suite_test'
        ])

        run_cmd = commands.get_command(args.command_name)
        # How do I resolve the configs without building the test?
        ret = run_cmd.run(self.pav_cfg, args)

        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[0]

        self.assertTrue(last_test.config["host"] == "host1")
        
        variables = last_test.config["variables"]

        self.assertEqual(variables.get("host1")[0].get(None), "True")

    def test_suites_mode_config(self):
        """Test that Pavilion loads mode configs from the
        suites directory"""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-m', 'mode1',
            'modes_suite_test'
        ])

        run_cmd = commands.get_command(args.command_name)
        # How do I resolve the configs without building the test?
        ret = run_cmd.run(self.pav_cfg, args)

        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[0]

        self.assertTrue("mode1" in last_test.config["modes"])
        
        variables = last_test.config["variables"]

        self.assertEqual(variables.get("mode1")[0].get(None), "True")

    def test_suites_platform_config(self):
        """Test that Pavilion loads platform configs from the
        suites directory"""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-p', 'platform1',
            'platforms_suite_test'
        ])

        run_cmd = commands.get_command(args.command_name)
        # How do I resolve the configs without building the test?
        ret = run_cmd.run(self.pav_cfg, args)

        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[0]

        self.assertTrue(last_test.config["platform"] == "platform1")
        
        variables = last_test.config["variables"]

        self.assertEqual(variables.get("platform1")[0].get(None), "True")

    def test_suites_build_hash(self):
        """Test that Pavilion ignores config files in the
        suites directory when computing the build hash."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'hash_suite_test_a'
        ])

        run_cmd = commands.get_command(args.command_name)
        ret = run_cmd.run(self.pav_cfg, args)

        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[0]
        hash_a = last_test.builder.build_hash

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'hash_suite_test_b'
        ])

        run_cmd = commands.get_command(args.command_name)
        ret = run_cmd.run(self.pav_cfg, args)

        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[0]
        hash_b = last_test.builder.build_hash

        self.assertEqual(hash_a, hash_b)

    def test_suite_with_source(self):
        """Test that Pavilion correctly finds and uses source files in the suites directory."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'suite_with_source'
        ])

        run_cmd = commands.get_command(args.command_name)
        ret = run_cmd.run(self.pav_cfg, args)

        self.assertEqual(ret, 0)
