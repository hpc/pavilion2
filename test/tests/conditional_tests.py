from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion.test_config import file_format
from pavilion import plugins
from pavilion.status_file import STATES
import os
import io
class ConditionalTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)


    def tearDown(self):
        plugins._reset_plugins()

    def test_only_if(self):

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
            self.assertEqual(tests[i].status.current().state, 'SCHEDULED')

    def test_not_if(self):
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
            'cond_failure.eight'])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()
        run_cmd.run(self.pav_cfg,args)
        tests = run_cmd.test_list
        for i in range(0,len(tests)):
             self.assertEqual(tests[i].status.current().state, 'SKIPPED')
