import argparse
import errno
import time
from io import StringIO

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase


class CancelCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_clean(self):
        """Test clean command with no arguments."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'clean_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'clean'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.silence()

        self.assertEqual(clean_cmd.run(self.pav_cfg, args), 0)

    def test_clean_wait(self):
        """Test clean command after waiting for tests to finish."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'clean_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        time.sleep(1)

        args = arg_parser.parse_args([
            'clean'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.silence()

        self.assertEqual(clean_cmd.run(self.pav_cfg, args), 0)

    def test_clean_with_older_than_flag(self):
        """Test clean command with multiple date formats."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'clean_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'clean',
            '--older-than', '5 weeks'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.silence()

        self.assertEqual(clean_cmd.run(self.pav_cfg, args), 0)

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'clean_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

