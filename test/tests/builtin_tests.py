from time import sleep

from pavilion import commands, plugins, arguments
from pavilion.unittest import PavTestCase


class BuiltinTests(PavTestCase):
    """Test Pavilion builtins."""

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def test_survey_mode_output_generated(self):
        run_cmd = commands.get_command('run')
        run_cmd.silence()
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            '-m', 'survey',
            'hello_c'
        ])

        ret = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[-1]
        test_dir = last_test.path
        survey_outfile = test_dir / 'build' / 'hello-survey-report.json'

        last_test.wait()

        sleep(0.2)

        self.assertTrue(survey_outfile.exists())

    def test_survey_results_parsing(self):
        run_cmd = commands.get_command('run')
        #run_cmd.silence()
        arg_parser = arguments.get_parser()

        args = arg_parser.parse_args([
            'run',
            '-H', 'this',
            '-m', 'survey',
            'hello_c'
        ])

        ret = run_cmd.run(self.pav_cfg, args)
        self.assertEqual(ret, 0)

        last_test = run_cmd.last_tests[-1]
        
        last_test.wait()

        sleep(0.2)

        self.assertTrue('survey' in last_test.results)
        self.assertTrue(len(last_test.results['survey']) > 0)
