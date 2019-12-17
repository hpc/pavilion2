import errno
import os
import io
import sys

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import utils
from pavilion.unittest import PavTestCase

class StatusTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def teatDown(self):
        plugins._reset_plugins()

    def test_ls(self):
        """Checking basic ls functionality"""
        test = self._quick_test()

        job_id = test.id

        ls_cmd = commands.get_plugin('ls')
        ls_cmd.outfile = io.StringIO()
        ls_cmd.errfile = io.StringIO()

        arg_parser = arguments.get_parser()
        arg_sets = (
            ['ls', job_id ],
            ['ls', job_id, '--tree']
            ['ls', job_id, 'build' ]
        )

        for arg_set in arg_sets:
            args = arg_parser.parse_args(arg_set)
            ls_cmd.run(args)
            utils.fprint(ls_cmd.outfile)
            utils.fprint(ls_cmd.errfile)

    def test_ls_error(self):
        """Checking ls error functionality"""
        test = self._quick_test()
        job_id = test.id
        utils.fprint("JOB ID: {}".format(str(job_id)))
        utils.fprint(str(job_id))
