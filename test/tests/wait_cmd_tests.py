from pavilion import commands
from pavilion import plugins
from pavilion.series import TestSeries
from pavilion.test_config import file_format, VariableSetManager
from pavilion.unittest import PavTestCase
from pavilion.test_run import TestRun
import argparse
import io


class WaitCmdTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_wait_command(self):
        """Test wait command."""

        config1 = file_format.TestConfigLoader().validate({
            'scheduler': 'raw',
            'run': {
                'env': {
                    'foo': 'bar',
                },
                'cmds': ['echo 0'],
            },
        })

        config1['name'] = 'run_test0'

        config2 = file_format.TestConfigLoader().validate({
            'scheduler': 'raw',
            'run': {
                'env': {
                    'too': 'tar',
                },
                'cmds': ['echo 1'],
            },
        })

        config2['name'] = 'run_test1'

        config3 = file_format.TestConfigLoader().validate({
            'scheduler': 'raw',
            'run': {
                'env': {
                    'too': 'tar',
                },
                'cmds': ['sleep 1'],
            },
        })

        config3['name'] = 'run_test2'

        configs = [config1, config2, config3]

        tests = [self._quick_test(config)
                 for config in configs]

        for test in tests:
            test.RUN_SILENT_TIMEOUT = 1

        # Make sure this doesn't explode
        suite = TestSeries(self.pav_cfg, tests)
        test_str = " ".join([str(test) for test in suite.tests])

        wait_cmd = commands.get_command('wait')
        wait_cmd.outfile = io.StringIO()

        # Testing for individual tests with json output
        for test in suite.tests:
            parser = argparse.ArgumentParser()
            wait_cmd._setup_arguments(parser)
            arg_list = ['-t', '1', str(test)]
            args = parser.parse_args(arg_list)
            self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)

        # Testing for multiple tests with json output
        parser = argparse.ArgumentParser()
        wait_cmd._setup_arguments(parser)
        arg_list = ['-t', '1'] + test_str.split()
        args = parser.parse_args(arg_list)
        self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)

        # Testing for individual tests with tabular output
        for test in suite.tests:
            parser = argparse.ArgumentParser()
            wait_cmd._setup_arguments(parser)
            arg_list = ['-t', '1', str(test)]
            args = parser.parse_args(arg_list)
            self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)

        # Testing for multiple tests with tabular output
        parser = argparse.ArgumentParser()
        wait_cmd._setup_arguments(parser)
        arg_list = ['-t', '1'] + test_str.split()
        args = parser.parse_args(arg_list)
        self.assertEqual(wait_cmd.run(self.pav_cfg, args), 0)
