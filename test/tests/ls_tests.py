import errno
import os
import sys

from pavilion import commands
from pavilion import utils
from pavilion.unittest import PavTestCase

class StatusTests(PavTestCase):

    def test_ls(self):
        """Checking basic ls functionality"""
        test = self._quick_test()
        job_id = test.id

        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'ls'
        ])
        utils.fprint("JOB ID: {}".format(str(job_id)))

    def test_ls_error(self):
        """Checking ls error functionality"""
        test = self._quick_test()
        job_id = test.id
        utils.fprint("JOB ID: {}".format(str(job_id)))
        utils.fprint(str(job_id))
