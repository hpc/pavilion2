import io
import os

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion.status_file import STATES
from pavilion.test_config import file_format, setup, variables
from pavilion.unittest import PavTestCase

class ConditionalTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_success(self): # this method runs some conditional successes

        sys_vars = {
             'sys_name': 'bieber',
             'sys_os': 'centos',
             'sys_arch': 'x86_64'}
        pav_vars = {}

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            'cond_success.one',
            'cond_success.two',
            'cond_success.three',
            'cond_success.four',
            'cond_success.five'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()
        run_cmd.run(self.pav_cfg,args)
        tests = run_cmd.test_list

        for i in range(0,len(tests)):
            cond = setup.cond_check(tests[i].config,pav_vars,sys_vars)
            self.assertTrue(len(cond)==0) #check if any matches occur

    def test_failure(self): #this method runs some conditional failures

        sys_vars = {
            'sys_name':'bieber',
            'sys_host':'centos',
            'sys_arch':'x86_64'}

        pav_vars = {}

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            'cond_failure.one',
            'cond_failure.two',
            'cond_failure.three',
            'cond_failure.four',
            'cond_failure.five',
            'cond_failure.six',
            'cond_failure.seven',
            'cond_failure.eight'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()
        run_cmd.run(self.pav_cfg,args)
        tests = run_cmd.test_list

        for i in range(0,len(tests)):
            cond = setup.cond_check(tests[i].config,pav_vars,sys_vars)
            self.assertTrue(len(cond)>0)


