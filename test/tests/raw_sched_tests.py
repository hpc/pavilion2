from pavilion import plugins
from pavilion import schedulers
from pavilion.test_config.format import TestConfigLoader
from pavilion.pavtest import PavTest
from pavilion.unittest import PavTestCase
from pavilion.status_file import STATES
import socket
import subprocess
from pathlib import Path
import os


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

        cfg = TestConfigLoader().validate({
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'echo "Hello World."'
                ]
            },
        })
        cfg['name'] = 'raw_test'

        self.test = PavTest(
            self.pav_cfg,
            cfg,
            sys_vars={}
        )

    def tearDown(self):

        plugins._reset_plugins()

    def test_sched_vars(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        raw = schedulers.get_scheduler_plugin('raw')

        svars = raw.get_vars(self.test)

        for key, value in svars.items():
            self.assertNotEqual(int(value), 0)

    def test_schedule_test(self):
        """Make sure the scheduler can run a test."""

        raw = schedulers.get_scheduler_plugin('raw')

        self.assertTrue(self.test.build())

        raw.schedule_tests(self.pav_cfg, [self.test])

        self.test.wait(2)

        self.assertEqual(self.test.status.current().state, STATES.COMPLETE)

    def test_check_job(self):
        """Make sure we can get the test's scheduler status."""

        cfg = TestConfigLoader().validate({
            'scheduler': 'raw',
            'run': {
                'cmds': [
                    'sleep 2"'
                ]
            },
        })
        cfg['name'] = 'raw_test'

        test = PavTest(
            self.pav_cfg,
            cfg,
            sys_vars={}
        )

        test.status.set('SCHEDULED', 'but not really')

        with Path('/proc/sys/kernel/pid_max').open() as pid_max_file:
            max_pid = int(pid_max_file.read())

        hostname = socket.gethostname()

        raw = schedulers.get_scheduler_plugin('raw')

        # Make a test from another host.
        test.job_id = 'garbledhostnameasldfkjasd_{}'.format(os.getpid())
        status = raw.check_job(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHEDULED)

        # Make a test with a non-existent pid.
        test.job_id = '{}_{}'.format(hostname, max_pid + 1)
        status = raw.check_job(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHED_ERROR)

        # Check the 'race condition' case of check_job
        test.status.set(STATES.COMPLETE, 'not really this either.')
        status = raw.check_job(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.COMPLETE)
        test.status.set(STATES.SCHEDULED, "reseting.")

        # Make a test with a re-used pid.
        test.job_id = '{}_{}'.format(hostname, os.getpid())
        status = raw.check_job(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHED_ERROR)

        raw.schedule_test(self.pav_cfg, test)
        status = raw.check_job(self.pav_cfg, test)
        self.assertEqual(status.state, STATES.SCHEDULED)
