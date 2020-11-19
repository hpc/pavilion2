import errno
import sys
from io import StringIO

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import series
from pavilion.plugins.commands.status import get_statuses
from pavilion.unittest import PavTestCase


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
            'cancel_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = run_cmd.errfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel'
        ])

        get_statuses(self.pav_cfg, args.tests, StringIO())

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_invalid_test(self):
        """Test cancel command with invalid test."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            '{}'.format(sys.maxsize)
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), errno.EINVAL)

    def test_cancel_series_test(self):
        """Test cancel command with combination of series and tests."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'cancel_test.test1',
            'cancel_test.test2'
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
        cancel_cmd.outfile = cancel_cmd.errfile = StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_status_flag(self):
        """Test cancel command with status flag."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'cancel_test.test1'
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

