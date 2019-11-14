from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase
from pavilion import arguments
from pavilion.test_config.file_format import TestConfigError
import io
import json


class RunCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_get_tests(self):
        """Make sure we can go through the whole process of getting tests.
            For the most part we're relying on tests of the various components
            of test_config.setup and the test_obj tests."""

        run_cmd = commands.get_command('run')

        tests = run_cmd._get_tests(
            pav_cfg=self.pav_cfg,
            host='this',
            test_files=[],
            tests=['hello_world'],
            modes=[],
            overrides={},
            sys_vars={})

        tests = run_cmd._configs_to_tests(
            pav_cfg=self.pav_cfg,
            sys_vars={},
            configs_by_sched=tests,
        )

        t1, t2 = tests['raw']
        # Make sure our tests are in the right order
        if t1.name != 'hello_world.hello':
            t1, t2 = t2, t1

        # Make sure all the tests are there, under the right schedulers.
        self.assertEqual(t1.name, 'hello_world.hello')
        self.assertEqual(t2.name, 'hello_world.world')
        self.assertEqual(tests['dummy'][0].name, 'hello_world.narf')

        tests_file = self.TEST_DATA_ROOT/'run_test_list'

        tests = run_cmd._get_tests(
            pav_cfg=self.pav_cfg,
            host='this',
            test_files=[tests_file],
            tests=[],
            modes=[],
            overrides={},
            sys_vars={})

        tests = run_cmd._configs_to_tests(
            pav_cfg=self.pav_cfg,
            sys_vars={},
            configs_by_sched=tests,
        )

        self.assertEqual(tests['raw'][0].name, 'hello_world.world')
        self.assertEqual(tests['dummy'][0].name, 'hello_world.narf')

    def test_run(self):

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            'hello_world.world',
            'hello_world.narf'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

    def test_run_status(self):
        '''Tests run command with status flag.'''

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-s',
            'hello_world'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()

        run_cmd.outfile = io.StringIO()

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

    def test_run_status_json(self):
        '''Tests run command with status and json flags'''

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-s', '-j',
            'hello_world'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()

        self.assertEqual(run_cmd.run(self.pav_cfg, args), 0)

        status = run_cmd.outfile.getvalue().split('\n')[-1].strip().encode('UTF-8')
        status = status[4:].decode('UTF-8')
        status = json.loads(status)

        self.assertNotEqual(len(status), 0)

    def test_build_src_location(self):
        """src_download_name and src_location"""

        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            'build_config.fine'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.outfile = io.StringIO()

        self.dbg_print(run_cmd.run(self.pav_cfg, args))

        with self.assertRaises(TestConfigError):
            arg_parser = arguments.get_parser()

            args = arg_parser.parse_args([
                'run',
                'build_config.not_fine'
            ])

            run_cmd = commands.get_command(args.command_name)
            run_cmd.outfile = io.StringIO()

            run_cmd.run(self.pav_cfg, args)