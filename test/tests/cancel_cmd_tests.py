"""Test the cancel command."""

import errno
import sys

import pavilion.series
from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.status_utils import get_statuses
from pavilion.unittest import PavTestCase


class CancelCmdTests(PavTestCase):

    def set_up(self):
        plugins.initialize_plugins(self.pav_cfg)
        commands.load('run', 'cancel')

    def test_cancel(self):
        """Test cancel command with no arguments."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'cancel_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel'
        ])

        get_statuses(self.pav_cfg, args.tests)

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.silence()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_invalid_test(self):
        """Test cancel command with invalid test."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            'test.{}'.format(sys.maxsize)
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.silence()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 22)

    def test_cancel_series(self):
        """Test cancel command with combination of series and tests."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'cancel_test.test1',
            'cancel_test.test2'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        tests = []

        series_id = pavilion.series.load_user_series_id(self.pav_cfg)
        tests.append(series_id)

        args = arg_parser.parse_args([
            'cancel',
            tests[0],
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.silence()

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
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel',
            '-s'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.silence()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

