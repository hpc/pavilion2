from pavilion import plugins
from pavilion import commands
from pavilion import schedulers
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion import series
from pavilion.test_run import TestRun
from pavilion.status_file import STATES
from pavilion.plugins.commands.status import get_statuses
from io import StringIO
import sys
import errno
import time
import json


class CancelCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_cancel(self):
        """Test cancel command with no arguments."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel'
        ])

        get_statuses(self.pav_cfg, args, StringIO())

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_sched_check(self):
        """Cancel Test and make sure it is cancelled through scheduler."""

        arg_parser = arguments.get_parser()

        # This test will just sleep for a bit.
        cfg = self._quick_test_cfg()
        cfg['run']['cmds'] = ['sleep 100']

        test = self._quick_test(cfg=cfg)
        test.build()

        raw = schedulers.get_scheduler_plugin('raw')

        raw.schedule_test(self.pav_cfg, test)

        timeout = time.time() + 1
        while (raw.job_status(self.pav_cfg, test).state == STATES.SCHEDULED
               and time.time() < timeout):
            time.sleep(.1)

        # The test should be running
        self.assertEqual(test.status.current().state,
                         STATES.RUNNING)

        self.assertEqual(raw.cancel_job(test).state, STATES.SCHED_CANCELLED)

        args = arg_parser.parse_args([
            'cancel'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        sched_status = raw.job_status(self.pav_cfg, test)
        self.assertIn("SCHED_CANCELLED", str(sched_status))

    def test_wait_cancel(self):
        """Test cancel command after waiting for tests to start."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel'
        ])

        time.sleep(5)
        get_statuses(self.pav_cfg, args, StringIO())

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_cancelled_test(self):
        """Test cancelling a previously cancelled test."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel'
        ])

        get_statuses(self.pav_cfg, args, StringIO())

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        cancel_cmd.run(self.pav_cfg, args)
        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_invalid_test(self):
        """Test cancel command with invalid test."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            '{}'.format(sys.maxsize)
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), errno.EINVAL)

    def test_cancel_invalid_series(self):
        """Test cancel command with invalid series."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            's{}'.format(sys.maxsize)
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), errno.EINVAL)

    def test_cancel_series_test(self):
        """Test cancel command with combination of series and tests."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world.hello',
            'hello_world.world'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        tests = []

        series_id = series.TestSeries.load_user_series_id(self.pav_cfg)
        tests.append(series_id)

        args = arg_parser.parse_args([
            'cancel',
            tests[0],
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = sys.stdout
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_status_flag(self):
        """Test cancel command with status flag."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world.world'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel',
            '-s'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_status_json(self):
        """Test cancel command with status flag and json flag."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world.world'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel',
            '-s', '-j'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = StringIO()
        cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

        results = cancel_cmd.outfile.getvalue().split('\n')[-1].strip().encode('UTF-8')
        results = results[4:].decode('UTF-8')
        results = json.loads(results)

        self.assertNotEqual(len(results), 0)
