import io
import time

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase
from pavilion.plugins.commands.status import get_statuses

class TimeoutFileTests(PavTestCase):
    """Assorted tests to ensure that timeout files work as expected."""

    def setUp(self):

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_build_timeouts(self):
        """Make sure build timeout file works as expected."""

        run_cmd = commands.get_command('run')
        run_cmd.silence()

        arg_parser = arguments.get_parser()

        # Successful build where timeout file is not created.
        args = arg_parser.parse_args([
            'run',
            'timeout_build_tests.GoodBuild'
        ])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        # Successful build after creating/touching timeout file.
        args = arg_parser.parse_args([
            'run',
            'timeout_build_tests.GoodBuild2'
        ])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        # Successful build after deleting timeout file.
        args = arg_parser.parse_args([
            'run',
            'timeout_build_tests.GoodBuild3'
        ])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        # Unsuccessful build, where timeout file is not created.
        args = arg_parser.parse_args([
            'run',
            'timeout_build_tests.BadBuild'
        ])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 22)

        # Unsuccessful build after creating/touching timeout file.
        args = arg_parser.parse_args([
            'run',
            'timeout_build_tests.BadBuild2'
        ])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 22)

        # Unsuccessful build after deleting timeout file.
        args = arg_parser.parse_args([
            'run',
            'timeout_build_tests.BadBuild3'
        ])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 22)

    def test_run_timeouts(self):
        """Make sure run timeout file works as expected."""

        run_cmd = commands.get_command('run')
        run_cmd.silence()

        arg_parser = arguments.get_parser()

        # All test follow the same pattern seen above, but we can run them all
        # at once, since a run timeout doesn't effect the others.
        args = arg_parser.parse_args([
            'run',
            'timeout_run_tests'
        ])
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        time.sleep(35)

        correct_statuses = {
            'timeout_run_tests.GoodRun': 'COMPLETE',
            'timeout_run_tests.GoodRun2': 'COMPLETE',
            'timeout_run_tests.GoodRun3': 'COMPLETE',
            'timeout_run_tests.BadRun': 'RUN_TIMEOUT',
            'timeout_run_tests.BadRun2': 'RUN_TIMEOUT',
            'timeout_run_tests.BadRun3': 'RUN_TIMEOUT'
        }

        status_args = arg_parser.parse_args([
            'status'
        ])

        statuses = get_statuses(self.pav_cfg, status_args.tests, io.StringIO())
        for test_status in statuses:
            self.assertEqual(correct_statuses[test_status['name']],
                             test_status['state'])
