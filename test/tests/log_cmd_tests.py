import argparse
import io
import sys
import threading
import time

from pavilion import commands
from pavilion import schedulers
from pavilion.unittest import PavTestCase


class LogCmdTest(PavTestCase):

    def test_log_arguments(self):
        log_cmd = commands.get_command('log')
        log_cmd.silence()

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        # run a simple test
        test = self._quick_test(finalize=False)
        raw = schedulers.get_plugin('raw')

        raw.schedule_tests(self.pav_cfg, [test])

        try:
            test.wait(self.testrun_wait_timeout)
        except TimeoutError:
            self.fail(f"Timed out waiting for test to complete after {self.testrun_wait_timeout} seconds.")

        # test `pav log run test`
        args = parser.parse_args(['run', str(test.id)])
        result = log_cmd.run(self.pav_cfg, args)
        out, err = log_cmd.clear_output()
        self.assertEqual(err, '')
        self.assertIn('Hello World.\n', out)
        self.assertEqual(result, 0)

        # test `pav log build test`
        # note: echo-ing hello world should not require anything to be built
        args = parser.parse_args(['build', str(test.id)])
        log_cmd.run(self.pav_cfg, args)
        out, err = log_cmd.clear_output()
        out_data = '\n'.join(line for line in out.split('\n')
                             if not line.startswith('(pav)'))

        self.assertEqual(out_data, '')

        # test `pav log kickoff test`
        # note: in general, kickoff.log should be an empty file
        args = parser.parse_args(['kickoff', str(test.id)])
        result = log_cmd.run(self.pav_cfg, args)
        out, err = log_cmd.clear_output()
        self.assertEqual(out, '')
        self.assertEqual(err, '')
        self.assertEqual(result, 0)

        # test 'pav log global'
        args = parser.parse_args((['global']))
        result = log_cmd.run(self.pav_cfg, args)
        out, err = log_cmd.clear_output()
        self.assertEqual(result, 0)
        self.assertEqual(err, '')

        # test 'pav log all_results'
        args = parser.parse_args(['all_results'])
        result = log_cmd.run(self.pav_cfg, args)
        self.assertEqual(result, 0)
        self.assertEqual(err, '')

    def test_log_tail(self):
        log_cmd = commands.get_command('log')
        log_cmd.silence()

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        # test 'pav log --tail X run test'
        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "this"', 'echo "is"', 'echo "some"',
                                   'echo "crazy"', 'echo "long"', 'echo "output"']
        test = self._quick_test(cfg=test_cfg)

        raw = schedulers.get_plugin('raw')
        raw.schedule_tests(self.pav_cfg, [test])

        try:
            test.wait(self.testrun_wait_timeout)
        except TimeoutError:
            self.fail(f"Timed out waiting for test to complete after {self.testrun_wait_timeout} seconds.")

        args = parser.parse_args(['--tail', '3', 'run', str(test.id)])
        result = log_cmd.run(self.pav_cfg, args)
        self.assertEqual(result, 0)
        out, err = log_cmd.clear_output()
        self.assertEqual(err, '')
        self.assertIn('long\noutput\n', out)

    def test_follow(self):
        log_cmd = commands.get_command('log')
        log_cmd.silence()

        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "this"', 'echo "is"', 'echo "some"',
                                   'echo "crazy"', 'echo "long"']
        test = self._quick_test(cfg=test_cfg)
        test.run()

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        args = parser.parse_args(['--follow', 'run', str(test.id)])
        thread = threading.Thread(target=log_cmd.run, args=(self.pav_cfg, args))
        thread.start()
        time.sleep(.2)
        with (test.path/'run.log').open('a') as runlog:
            runlog.write('output \n')

        try:
            thread.join(timeout=self.log_cmd_timeout)
        except TimeoutError:
            self.fail("Timed out waiting for log command to complete after "
                      f"{self.log_cmd_timeout} seconds.")

        out, err = log_cmd.clear_output()
        self.assertIn('output', out)
        log_cmd.follow_testing = True

    def test_log_states(self):
        """Test the 'log states' command."""


        test = self._quick_test()

        log_cmd = commands.get_command('log')
        log_cmd.silence()

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        for args in (
                ('states', str(test.id)),
                ('states', '--raw', str(test.id)),
                ('states', '--raw_time', str(test.id)),
                ('states', '--raw', '--raw_time', str(test.id)),
                ):
            args = parser.parse_args(args)
            self.assertEqual(log_cmd.run(self.pav_cfg, args), 0)
