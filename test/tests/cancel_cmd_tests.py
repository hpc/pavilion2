from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion.plugins.commands.status import get_statuses
import io
import sys

class CancelCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_cancel(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world'
        ])
        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()
        run_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cancel'
        ])

        get_statuses(self.pav_cfg, args, io.StringIO())

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = io.StringIO()
        cancel_cmd.errfile = io.StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_invalid_test(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            '{}'.format(sys.maxsize)
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = io.StringIO()
        cancel_cmd.errfile = io.StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_invalid_series(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            's{}'.format(sys.maxsize)
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = io.StringIO()
        cancel_cmd.errfile = io.StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_series_test(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            's23', '124', 's2'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = io.StringIO()
        cancel_cmd.errfile = io.StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_status_flag(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            '-s'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = io.StringIO()
        cancel_cmd.errfile = io.StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)

    def test_cancel_status_json(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'cancel',
            '-s', '-j'
        ])

        cancel_cmd = commands.get_command(args.command_name)
        cancel_cmd.outfile = io.StringIO()
        cancel_cmd.errfile = io.StringIO()

        self.assertEqual(cancel_cmd.run(self.pav_cfg, args), 0)
