import errno
import os
import io
import sys

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import output
from pavilion.unittest import PavTestCase

class StatusTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def teatDown(self):
        plugins._reset_plugins()

    def test_ls(self):
        """Checking ls command functionality"""
        test = self._quick_test()

        ls_cmd = commands.get_command('ls')
        ls_cmd.outfile = io.StringIO()
        ls_cmd.errfile = io.StringIO()

        arg_parser = arguments.get_parser()
        arg_sets = (
            ['ls', str(test.id)],
            ['ls', str(test.id), '--tree'],
            ['ls', str(test.id), '--subdir', 'build' ],
        )

        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            ls_cmd.run(self.pav_cfg, args)
