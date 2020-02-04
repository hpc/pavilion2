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

    def test_cat(self):
        """Checking cat command functionality"""
        test = self._quick_test()

        cat_cmd = commands.get_command('cat')
        cat_cmd.outfile = io.StringIO()
        cat_cmd.errfile = io.StringIO()

        arg_parser = arguments.get_parser()
        arg_sets = (['cat', str(test.id), 'run.tmpl'],)
        true_out="""
#!/bin/bash

# The first (and only) argument of the build script is the test id.
export TEST_ID={}
export PAV_CONFIG_FILE={}
source {}

# Perform the sequence of test commands.
echo "Hello World."
""".format(some_var, some_var, some_var)

        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            cat_cmd.run(self.pav_cfg, args)
            # FIXME: always true
            if cat_cmd.run != true_out:
                return errno.ENOMSG
