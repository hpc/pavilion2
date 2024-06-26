import io
import os
import shutil

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.status_file import STATES
from pavilion.unittest import PavTestCase


class RunCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)
        run_cmd = commands.get_command('run')
        run_cmd.silence()

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

    def test_verbosity(self):
        """Run at all levels of verbosity, to make better explode."""

        arg_parser = arguments.get_parser()
        run_cmd = commands.get_command('run')

        for arg_set in [
            ('run', '-H', 'this', 'hello_world'),
            ('run', '-v', 'QUIET', '-H', 'this', 'hello_world'),
            ('run', '-v', 'DYNAMIC', '-H', 'this', 'hello_world'),
            ('run', '-v', 'HIGH', '-H', 'this', 'hello_world'),
            ('run', '-v', 'MAX', '-H', 'this', 'hello_world'),]:

            args = arg_parser.parse_args(arg_set)
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

        run_cmd = commands.get_command(args.command_name)
        run_ret = run_cmd.run(self.pav_cfg, args)

        run_cmd.outfile.seek(0)
        self.assertEqual(run_ret, 0, msg=run_cmd.outfile.read())

        for test in run_cmd.last_tests:
            test.wait(timeout=10)

        # Make sure we actually built separate builds
        builds = [test.builder for test in run_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        for test in run_cmd.last_tests:
            if test.skipped:
                continue
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

        run_cmd = commands.get_command(args.command_name)

        self.assertNotEqual(run_cmd.run(self.pav_cfg, args), 0)

        # Make sure we actually built separate builds
        builds = [test.builder for test in run_cmd.last_tests]
        build_names = set([b.name for b in builds])
        self.assertEqual(len(build_names), 4)

        run_cmd.last_series.wait()

        statuses = set([test.status.current().state for test in run_cmd.last_tests])
        self.assertEqual(statuses, {STATES.ABORTED, STATES.BUILD_FAILED})

        self.assertTrue(all([test.complete for test in
                             run_cmd.last_tests]))

    def test_build_parallel_lots(self):
        """Make sure building works beyond the parallel building limit."""

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'build_parallel_lots'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_ret = run_cmd.run(self.pav_cfg, args)

        run_cmd.outfile.seek(0)
        self.assertEqual(run_ret, 0, msg=run_cmd.outfile.read())

        for test in run_cmd.last_tests:
            test.wait(timeout=10)

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

    def test_run_repeat(self):
        """Check that run repeat functionality works as expected."""

        # Check with repeat flag.
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run', '--repeat', '3', 'hello_world.hello'
        ])
        run_cmd = commands.get_command(args.command_name)
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0, msg=run_cmd.clear_output())
        self.assertEqual(len(run_cmd.last_tests), 3)

        # Check with * notation.
        args = arg_parser.parse_args([
            'run', 'hello_world.hello*5'
        ])
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0, msg=run_cmd.clear_output())
        self.assertEqual(len(run_cmd.last_tests), 5)

        args = arg_parser.parse_args([
            'run', '5*hello_world.hello'
        ])
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        self.assertEqual(len(run_cmd.last_tests), 5)

        # Check with * notation and --repeat flag.
        args = arg_parser.parse_args([
            'run', '--repeat', '2', 'hello_world.hello*2'
        ])
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)
        self.assertEqual(len(run_cmd.last_tests), 4)

        # Check with invalid arguments
        args = arg_parser.parse_args([
            'run', 'hello_world.hello*two'
        ])
        self.assertNotEqual(run_cmd.run(self.pav_cfg, args), 0)

    def test_run_file(self):
        """Check that the -f argument for pav run works. """

        arg_parser = arguments.get_parser()

        # pass a collection name to -f (not an absolute path)
        args = arg_parser.parse_args([
            'run',
            '-f', 'testlist.txt',
        ])

        run_cmd = commands.get_command(args.command_name)

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

    def test_concurrent(self):
        """Check that concurrency works."""

        arg_parser = arguments.get_parser()

        try:
            shutil.rmtree('/tmp/pav_concurrent')
            os.unlink('/tmp/pav_concurrent.count')
        except OSError:
            pass

        # pass a collection name to -f (not an absolute path)
        args = arg_parser.parse_args(['run', 'concurrent'])
        run_cmd = commands.get_command(args.command_name)
        out, err = run_cmd.clear_output()
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0, msg=out+err)

        run_cmd.last_series.wait()

        # The test fails if it ever catches more tests running than its concurrency limit
        for test in run_cmd.last_tests:
            self.assertEqual(test.result, 'PASS')

        # Ensure than more than one test is running simultaniously at some point.
        with open('/tmp/pav_concurrent.count') as f:
            lines = f.readlines()
        counts = [int(c) for c in lines if c]
        self.assertGreater(max(counts), 1)

        shutil.rmtree('/tmp/pav_concurrent')
        os.unlink('/tmp/pav_concurrent.count')
