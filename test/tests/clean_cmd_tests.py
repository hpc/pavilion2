from pavilion import plugins
from pavilion import commands
from pavilion import arguments
from pavilion.unittest import PavTestCase
from pavilion.pav_test import PavTest
from pavilion.status_file import STATES
from io import StringIO
import sys
import errno
import time

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
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'clean'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.outfile = StringIO()
        clean_cmd.errfile = StringIO()

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
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        time.sleep(5)

        args = arg_parser.parse_args([
            'clean'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.outfile = StringIO()
        clean_cmd.errfile = StringIO()

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
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'clean',
            '--older-than', '5', 'weeks'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.outfile = StringIO()
        clean_cmd.errfile = StringIO()

        self.assertEqual(clean_cmd.run(self.pav_cfg, args), 0)

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'clean_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'clean',
            '--older-than', 'Jul', '3', '2019'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.outfile = StringIO()
        clean_cmd.errfile = StringIO()

        self.assertEqual(clean_cmd.run(self.pav_cfg, args), 0)

    def test_clean_with_invalid_date(self):
        """Test clean command with invalid arguments."""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'clean_test'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'clean',
            '--older-than', '5', 'foo'
        ])

        clean_cmd = commands.get_command(args.command_name)
        clean_cmd.outfile = StringIO()
        clean_cmd.errfile = StringIO()

        self.assertEqual(clean_cmd.run(self.pav_cfg, args), errno.EINVAL)

