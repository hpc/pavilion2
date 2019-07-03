from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase
import argparse

class LogCmdTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_log_arguments(self):
        log_cmd = commands.get_command('log')

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        # test `pav log run test`
        args = parser.parse_args(['run', 'test'])
        self.assertEqual(args.test, 'test')

        # test `pav log kickoff test`
        args = parser.parse_args(['kickoff', 'test'])
        self.assertEqual(args.test, 'test')

        # test `pav log kickoff test`     
        args = parser.parse_args(['kickoff', 'test'])
        self.assertEqual(args.test, 'test')

    def test_log_command(self):
        """Test log command by generator a suite of tests."""
