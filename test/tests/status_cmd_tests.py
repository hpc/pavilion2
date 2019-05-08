from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase
import argparse


class StatusTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_status_arguments(self):
        status_cmd = commands.get_command('status')

        parser = argparse.ArgumentParser()
        status_cmd._setup_arguments(parser)
        args = parser.parse_args(['test1','test2'])

        self.assertEqual(args.tests[0], 'test1')
        self.assertEqual(args.tests[1], 'test2')
        self.assertEqual(args.json, False)

        parser = argparse.ArgumentParser()
        status_cmd._setup_arguments(parser)
        args = parser.parse_args(['-j','test0','test9'])

        self.assertEqual(args.tests[0], 'test0')
        self.assertEqual(args.tests[1], 'test9')
        self.assertEqual(args.json, True)

