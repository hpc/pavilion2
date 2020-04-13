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

    def tearDown(self):
        plugins._reset_plugins()

    def test_cat(self):
        """Checking cat command functionality"""
        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "hello world"'] * 10
        test = self._quick_test(test_cfg)

        cat_cmd = commands.get_command('cat')
        cat_cmd.outfile = cat_cmd.errfile = io.StringIO()

        arg_parser = arguments.get_parser()
        arg_sets = (['cat', str(test.id), 'run.tmpl'],)
        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            cat_cmd.run(self.pav_cfg, args)

            with open(str(test.path/arg_set[-1]), 'r') as out_file:
                true_out = out_file.read()
                cat_out = cat_cmd.outfile.getvalue()
                self.assertEqual(cat_out, true_out)
