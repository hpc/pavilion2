"""Test command utility functions."""

import io
import json
import shutil
from pathlib import Path

from pavilion import dir_db
from pavilion import unittest
from pavilion import cmd_utils
from pavilion import commands
from pavilion import arguments


class CmdUtilsTests(unittest.PavTestCase):

    def test_load_last_series(self):
        """Checking loading the previous series."""

        run_cmd = commands.get_command('run')
        run_cmd.silence()

        args = arguments.get_parser().parse_args(['run', 'hello_world'])

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        last_series = cmd_utils.load_last_series(self.pav_cfg, io.StringIO())

        self.assertEqual(last_series.sid, run_cmd.last_series.sid)

    def test_arg_filtered_tests(self):
        """Make sure basic requests for tests work."""

        run_cmd = commands.get_command('run')
        run_cmd.silence()
        args = arguments.get_parser().parse_args(['run', 'arg_filtered'])
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        series1 = run_cmd.last_series

        args = arguments.get_parser().parse_args(['run', 'hello_world'])
        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        series2 = run_cmd.last_series

        # This just loads the arguments for the status command.
        commands.get_command('status')

        tests1 = [test.full_id for test in series1.tests.values()]

        for argset, count in [
                (('status', series1.sid, series2.sid), 6),
                (('status', '{}-{}'.format(series1.sid, series2.sid)), 6),
                (('status', 'all', '--filter', 'name=arg_filtered.*'), 3),
                (('status', ) + tuple(tests1), 3),
                ]:

            args = arguments.get_parser().parse_args(argset)

            self.assertEqual(len(cmd_utils.arg_filtered_tests(self.pav_cfg, args).paths), count)

    # TODO: We really need to add unit tests for each of the cmd utils functions.
