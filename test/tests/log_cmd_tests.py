import argparse
import io
import sys
import threading
import time

import pavilion.commands
import pavilion.schedulers
from pavilion.unittest import PavTestCase


class LogCmdTest(PavTestCase):

    def test_log_arguments(self):
        log_cmd = pavilion.commands.get_command('log')

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        # run a simple test
        test = self._quick_test(finalize=False)
        raw = pavilion.schedulers.get_plugin('raw')

        raw.schedule_tests(self.pav_cfg, [test])

        end = time.time() + 5

        while not test.complete and time.time() < end:
            time.sleep(.1)

        # test `pav log run test`
        args = parser.parse_args(['run', test.full_id])

        out = io.StringIO()
        err = io.StringIO()

        log_cmd.outfile = out
        log_cmd.errfile = err

        result = log_cmd.run(self.pav_cfg, args)
        err.seek(0)
        out.seek(0)
        self.assertEqual(err.read(), '')
        self.assertEqual(out.read(), 'Hello World.\n')
        self.assertEqual(result, 0)

        # test `pav log build test`
        # note: echo-ing hello world should not require anything to be built
        out.truncate(0)
        err.truncate(0)
        args = parser.parse_args(['build', test.full_id])
        log_cmd.run(self.pav_cfg, args)
        out.seek(0)
        err.seek(0)
        self.assertEqual(out.read(), '')

        # test `pav log kickoff test`
        # note: in general, kickoff.log should be an empty file
        out.truncate(0)
        err.truncate(0)
        args = parser.parse_args(['kickoff', test.full_id])
        result = log_cmd.run(self.pav_cfg, args)
        out.seek(0)
        err.seek(0)
        self.assertEqual(out.getvalue(), '')
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(result, 0)

        # test 'pav log global'
        out.truncate(0)
        err.truncate(0)
        args = parser.parse_args((['global']))
        result = log_cmd.run(self.pav_cfg, args)
        out.seek(0)
        err.seek(0)
        self.assertEqual(result, 0)
        self.assertEqual(err.getvalue(), '')

        # test 'pav log all_results'
        out.truncate(0)
        err.truncate(0)
        args = parser.parse_args(['all_results'])
        result = log_cmd.run(self.pav_cfg, args)
        out.seek(0)
        err.seek(0)
        self.assertEqual(result, 0)
        self.assertEqual(err.getvalue(), '')

    def test_log_tail(self):
        log_cmd = pavilion.commands.get_command('log')

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        out = io.StringIO()
        err = io.StringIO()

        log_cmd.outfile = out
        log_cmd.errfile = err

        # test 'pav log --tail X run test'
        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "this"', 'echo "is"', 'echo "some"',
                                   'echo "crazy"', 'echo "long"', 'echo "output"']
        test = self._quick_test(cfg=test_cfg)

        raw = pavilion.schedulers.get_plugin('raw')
        raw.schedule_tests(self.pav_cfg, [test])

        end = time.time() + 5
        while not test.complete and time.time() < end:
            time.sleep(.1)

        args = parser.parse_args(['--tail', '2', 'run', test.full_id])
        out.truncate(0)
        err.truncate(0)
        result = log_cmd.run(self.pav_cfg, args)
        self.assertEqual(result, 0)
        out.seek(0)
        err.seek(0)
        self.assertEqual(err.read(), '')
        self.assertEqual(out.read(), 'long\noutput\n')

        log_cmd.outfile = sys.stdout
        log_cmd.outfile = sys.stderr

    def test_follow(self):
        log_cmd = pavilion.commands.get_command('log')
        log_cmd.silence()

        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['echo "this"', 'echo "is"', 'echo "some"',
                                   'echo "crazy"', 'echo "long"']
        test = self._quick_test(cfg=test_cfg)
        test.run()

        parser = argparse.ArgumentParser()
        log_cmd._setup_arguments(parser)

        args = parser.parse_args(['--follow', 'run', test.full_id])
        thread = threading.Thread(target=log_cmd.run, args=(self.pav_cfg, args))
        thread.start()
        time.sleep(.2)
        with (test.path/'run.log').open('a') as runlog:
            runlog.write('output \n')
        thread.join(timeout=5)
        out, err = log_cmd.clear_output()
        self.assertIn('output', out)
        log_cmd.follow_testing = True
