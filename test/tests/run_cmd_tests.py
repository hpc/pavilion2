from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion import arguments


class RunCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_get_tests(self):
        """Make sure we can go through the whole process of getting tests.
            For the most part we're relying on tests of the various components
            of test_config.setup and the test_obj tests."""

        run_cmd = commands.get_command('run')

        tests = run_cmd._get_tests(
            pav_cfg=self.pav_cfg,
            host='this',
            test_files=[],
            tests=['hello_world'],
            modes=[],
            overrides={},
            sys_vars={})

        tests = run_cmd._configs_to_tests(
            pav_cfg=self.pav_cfg,
            sys_vars={},
            configs_by_sched=tests,
        )

        t1, t2 = tests['raw']
        # Make sure our tests are in the right order
        if t1.name != 'hello':
            t1, t2 = t2, t1

        # Make sure all the tests are there, under the right schedulers.
        self.assertEqual(t1.name, 'hello')
        self.assertEqual(t2.name, 'world')
        self.assertEqual(tests['dummy'][0].name, 'narf')

        tests_file = self.TEST_DATA_ROOT/'run_test_list'

        tests = run_cmd._get_tests(
            pav_cfg=self.pav_cfg,
            host='this',
            test_files=[tests_file],
            tests=[],
            modes=[],
            overrides={},
            sys_vars={})

        tests = run_cmd._configs_to_tests(
            pav_cfg=self.pav_cfg,
            sys_vars={},
            configs_by_sched=tests,
        )

        self.assertEqual(tests['raw'][0].name, 'world')
        self.assertEqual(tests['dummy'][0].name, 'narf')

    def test_run(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world.world',
            'hello_world.narf'
        ])

        run_cmd = commands.get_command(args.command_name)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)





