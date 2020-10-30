from pavilion import plugins
from pavilion import commands
from pavilion import cmd_utils
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion.plugins.commands.run import RunCommand
from pavilion.status_file import STATES
import io
import sys
import logging


class RunCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        run_cmd = commands.get_command('run')
        run_cmd.outfile = io.StringIO()
        run_cmd.errfile = run_cmd.outfile
        self.logger = logging.getLogger('unittest.RunCmdTests')

    def tearDown(self):
        plugins._reset_plugins()

    def test_get_tests(self):
        """Make sure we can go through the whole process of getting tests.
            For the most part we're relying on tests of the various components
            of test_config.setup and the test_obj tests."""

        test_configs = cmd_utils.get_test_configs(pav_cfg=self.pav_cfg,
                                                  host='this', test_files=[],
                                                  tests=['hello_world'],
                                                  modes=[],
                                                  overrides={},
                                                  outfile=sys.stdout
                                                  )

        tests = cmd_utils.configs_to_tests(
            pav_cfg=self.pav_cfg,
            proto_tests=test_configs,
        )

        # Make sure all the tests are there, under the right schedulers.
        for test in tests:
            if test.scheduler == 'raw':
                self.assertIn(test.name, ['hello_world.hello', 'hello_world.world'])
            else:
                self.assertEqual(test.name, 'hello_world.narf')

        tests_file = self.TEST_DATA_ROOT/'run_test_list'

        test_configs = cmd_utils.get_test_configs(pav_cfg=self.pav_cfg,
                                                  host='this',
                                                  test_files=[tests_file],
                                                  tests=[], modes=[],
                                                  overrides={},
                                                  outfile=sys.stdout)

        tests = cmd_utils.configs_to_tests(
            pav_cfg=self.pav_cfg,
            proto_tests=test_configs,
        )

        for test in tests:
            if test.name == 'hello_world.world':
                self.assertEqual(test.scheduler, 'raw')
            else:
                self.assertEqual(test.scheduler, 'dummy')

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
            test.wait(timeout=4)

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

        self.assertTrue(all([test.check_run_complete() for test in
                             run_cmd.last_tests]))

    def test_build_parallel_lots(self):
        """Make sure building works beyond the parallel building limit."""

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

    def test_no_sched(self):
        """Check that we get a reasonable error for a non-available
        scheduler."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run', 'not_available'
        ])

        run_cmd = commands.get_command(args.command_name)
        self.assertNotEqual(run_cmd.run(self.pav_cfg, args), 0)
