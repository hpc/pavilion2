"""Tests for the wait command"""

import argparse
import io

from pavilion import commands
from pavilion.series.series import TestSeries
from pavilion.unittest import PavTestCase


class WaitCmdTests(PavTestCase):

    def test_wait_command(self):
        """Test wait command."""

        sleepy_test = self._quick_test_cfg()
        sleepy_test['run']['cmds'] = ['sleep 1']

        tests = [self._quick_test(name='quick2'), self._quick_test(name='quick1'),
                 self._quick_test(sleepy_test, name='sleepy')]

        for test in tests:
            test.RUN_SILENT_TIMEOUT = 1

        # Make sure this doesn't explode
        series = TestSeries(self.pav_cfg, None)
        for test in tests:
            series._add_test('test_set', test)
        test_str = " ".join([test.full_id for test in series.tests.values()])

        wait_cmd = commands.get_command('wait')
        wait_cmd.outfile = io.StringIO()

        # Testing for individual tests with json output
        for test in series.tests.values():
            parser = argparse.ArgumentParser()
            wait_cmd._setup_arguments(parser)
            arg_list = ['-t', '1', test.full_id]
            args = parser.parse_args(arg_list)
            self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)

        # Testing for multiple tests with json output
        parser = argparse.ArgumentParser()
        wait_cmd._setup_arguments(parser)
        arg_list = ['-t', '1'] + test_str.split()
        args = parser.parse_args(arg_list)
        self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)

        # Testing for individual tests with tabular output
        for test in series.tests.values():
            parser = argparse.ArgumentParser()
            wait_cmd._setup_arguments(parser)
            arg_list = ['-t', '1', test.full_id]
            args = parser.parse_args(arg_list)
            self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)

        # Testing for multiple tests with tabular output
        parser = argparse.ArgumentParser()
        wait_cmd._setup_arguments(parser)
        arg_list = ['-t', '1'] + test_str.split()
        args = parser.parse_args(arg_list)
        self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)
