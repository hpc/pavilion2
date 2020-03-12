from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion.plugins.commands.run import RunCommand
from pavilion.status_file import STATES
import io


class RunCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        run_cmd = commands.get_command('run')
        run_cmd.outfile = io.StringIO()
        run_cmd.errfile = run_cmd.outfile

    def tearDown(self):
        plugins._reset_plugins()

    def test_get_tests(self):
        """Make sure we can go through the whole process of getting tests.
            For the most part we're relying on tests of the various components
            of test_config.setup and the test_obj tests."""

        run_cmd = commands.get_command('run')  # type: RunCommand

        configs_by_sched = run_cmd._get_test_configs(
            pav_cfg=self.pav_cfg,
            host='this',
            test_files=[],
            tests=['hello_world'],
            modes=[],
            overrides={},
            sys_vars={})

        tests = run_cmd._configs_to_tests(
            pav_cfg=self.pav_cfg,
            configs_by_sched=configs_by_sched,
        )

        t1, t2 = tests['raw']
        # Make sure our tests are in the right order
        if t1.name != 'hello_world.hello':
            t1, t2 = t2, t1

        # Make sure all the tests are there, under the right schedulers.
        self.assertEqual(t1.name, 'hello_world.hello')
        self.assertEqual(t2.name, 'hello_world.world')
        self.assertEqual(tests['dummy'][0].name, 'hello_world.narf')

        tests_file = self.TEST_DATA_ROOT/'run_test_list'

        configs_by_sched = run_cmd._get_test_configs(
            pav_cfg=self.pav_cfg,
            host='this',
            test_files=[tests_file],
            tests=[],
            modes=[],
            overrides={},
            sys_vars={})

        tests = run_cmd._configs_to_tests(
            pav_cfg=self.pav_cfg,
            configs_by_sched=configs_by_sched,
        )

        self.assertEqual(tests['raw'][0].name, 'hello_world.world')
        self.assertEqual(tests['dummy'][0].name, 'hello_world.narf')

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

    def test_multi_build(self):
        """Make sure we can build multiple simultanious builds on
        both the front-end and the nodes."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'build_parallel'
        ])

        run_cmd = commands.get_command(args.command_name)  # type: RunCommand
        run_ret = run_cmd.run(self.pav_cfg, args)

        run_cmd.outfile.seek(0)
        self.assertEqual(run_ret, 0, msg=run_cmd.outfile.read())

        for test in run_cmd.last_tests:
            test.wait(timeout=2)

        # Make sure we actually built separate builds
        builds = [test.builder for test in run_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        for test in run_cmd.last_tests:
            self.assertEqual(test.results['result'], 'PASS',
                             msg='Test {} status: {}'
                                 .format(test.id, test.status.current()))

    def test_multi_build_fail(self):
        """Make sure we can build multiple simultanious builds on
        both the front-end and the nodes."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'build_parallel_fail'
        ])

        run_cmd = commands.get_command(args.command_name)  # type: RunCommand

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 22)

        # Make sure we actually built separate builds
        builds = [test.builder for test in run_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        statuses = [test.status.current().state for test in run_cmd.last_tests]
        statuses = set(statuses)
        self.assertEqual(statuses, {STATES.ABORTED, STATES.BUILD_FAILED})

        self.assertTrue(all([test.complete for test in run_cmd.last_tests]))

    def test_build_parallel_lots(self):
        """Make building works beyond the parallel building limit."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'build_parallel_lots'
        ])

        run_cmd = commands.get_command(args.command_name)  # type: RunCommand
        run_ret = run_cmd.run(self.pav_cfg, args)

        run_cmd.outfile.seek(0)
        self.assertEqual(run_ret, 0, msg=run_cmd.outfile.read())

        for test in run_cmd.last_tests:
            test.wait(timeout=5)

        # Make sure we actually built separate builds
        builds = [test.builder for test in run_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 8)

        for test in run_cmd.last_tests:
            self.assertEqual(test.results['result'], 'PASS',
                             msg='Test {} status: {}'
                             .format(test.id, test.status.current()))

    def test_run_status(self):
        """Tests run command with status flag."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-s',
            'hello_world',
        ])

        run_cmd = commands.get_command(args.command_name)
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

