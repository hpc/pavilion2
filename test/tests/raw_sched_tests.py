import os
import socket
import subprocess
import time
from pathlib import Path

from pavilion import plugins
from pavilion import schedulers
from pavilion.status_file import STATES
from pavilion.unittest import PavTestCase

_HAS_SLURM = None


def has_slurm():
    global _HAS_SLURM
    if _HAS_SLURM is None:
        try:
            _HAS_SLURM = subprocess.call(['sinfo', '--version']) == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            _HAS_SLURM = False

    return _HAS_SLURM


class RawSchedTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def setUp(self):

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_sched_vars(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        raw = schedulers.get_scheduler_plugin('raw')

        svars = raw.get_vars(self._quick_test())

        for key, value in svars.items():
            self.assertNotEqual(int(value), 0)

    def test_schedule_test(self):
        """Make sure the scheduler can run a test."""

        raw = schedulers.get_scheduler_plugin('raw')

        test = self._quick_test()

        self.assertTrue(test.build())

        raw.schedule_tests(self.pav_cfg, [test])

        try:
            test.wait(2)
        except:
            self.dbg_print((test.path/'kickoff.log').open().read())
            self.fail()

        self.assertEqual(test.status.current().state, STATES.COMPLETE)

    def test_check_job(self):
        """Make sure we can get the test's scheduler status."""

        cfg = self._quick_test_cfg()
        cfg['run']['cmds'] = ['sleep 2']
        test = self._quick_test(cfg=cfg)

        test.status.set('SCHEDULED', 'but not really')

        with Path('/proc/sys/kernel/pid_max').open() as pid_max_file:
            max_pid = int(pid_max_file.read())

        hostname = socket.gethostname()

        raw = schedulers.get_scheduler_plugin('raw')

        # Make a test from another host.
        test.job_id = 'garbledhostnameasldfkjasd_{}'.format(os.getpid())
        status = raw.job_status(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHEDULED)

        # Make a test with a non-existent pid.
        test.job_id = '{}_{}'.format(hostname, max_pid + 1)
        status = raw.job_status(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHED_ERROR)

        # Check the 'race condition' case of check_job
        test.status.set(STATES.COMPLETE, 'not really this either.')
        status = raw.job_status(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.COMPLETE)
        test.status.set(STATES.SCHEDULED, "reseting.")

        # Make a test with a re-used pid.
        test.job_id = '{}_{}'.format(hostname, os.getpid())
        status = raw.job_status(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHED_ERROR)

        raw.schedule_test(self.pav_cfg, test)
        status = raw.job_status(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHEDULED)

    def test_cancel_job(self):
        """Create a series of tests and kill them under different
        circumstances."""

        # This test will just sleep for a bit.
        cfg = self._quick_test_cfg()
        cfg['run']['cmds'] = ['sleep 100']

        test = self._quick_test(cfg=cfg)
        test.build()

        raw = schedulers.get_scheduler_plugin('raw')

        raw.schedule_test(self.pav_cfg, test)

        timeout = time.time() + 1
        while (raw.job_status(self.pav_cfg, test).state == STATES.SCHEDULED
                and time.time() < timeout):
            time.sleep(.1)

        # The test should be running
        self.assertEqual(test.status.current().state,
                         STATES.RUNNING)

        _, pid = test.job_id.split('_')

        self.assertEqual(raw.cancel_job(test).state, STATES.SCHED_CANCELLED)
