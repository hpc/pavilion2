from pavilion import config
from pavilion import plugins
from pavilion import schedulers
from pavilion.unittest import PavTestCase
from pavilion.test_config.format import TestConfigLoader
from pavilion.status_file import STATES
from pavilion.pav_test import PavTest
import subprocess
import unittest


_HAS_SLURM = None


def has_slurm():
    global _HAS_SLURM
    if _HAS_SLURM is None:
        try:
            _HAS_SLURM = subprocess.call(['sinfo', '--version']) == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            _HAS_SLURM = False

    return _HAS_SLURM


class SlurmTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        # Do a default pav config, which will load from
        # the pavilion lib path.
        self.pav_config = config.PavilionConfigLoader().load_empty()

    def setUp(self):

        plugins.initialize_plugins(self.pav_config)

    def tearDown(self):

        plugins._reset_plugins()

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_job_status(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        slurm = schedulers.get_scheduler_plugin('slurm')

        cfg = TestConfigLoader().validate({
            'scheduler': 'slurm',
            'run': {
                'cmds': [
                    'echo "Hello World."'
                ]
            },
        })
        cfg['name'] = 'slurm_test'

        test = PavTest(self.pav_cfg, cfg, {})
        test.status.set(STATES.SCHEDULED, "not really though.")

        # Grab a random jobid, and get the status of it.
        jobs = subprocess.check_output(['squeue', '-o', "%i %T"])
        jobs = jobs.decode('utf-8')
        try:
            last_job = jobs.strip().split('\n')[-1]
            jobid, status = last_job.strip().split()
        except Exception:
            raise RuntimeError("No available test from which to borrow a"
                               "job id.")
        test.job_id = jobid

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_sched_vars(self):
        """Make sure the scheduler vars are reasonable."""

        slurm = schedulers.get_scheduler_plugin('slurm')

        cfg = TestConfigLoader().validate({
            'scheduler': 'slurm',
            'run': {
                'cmds': [
                    'echo "Hello World."'
                ]
            },
        })
        cfg['name'] = 'slurm_test'

        test = PavTest(self.pav_cfg, cfg, {})

        for k, v in slurm.get_vars(test).items():
            # Make sure everything has a value of some sort.
            self.assertNotIn(v, ['None', ''])

        # There's not much we can do to automatically test deferred slurm
        # vars without a dedicated slurm host. Maybe we'll set up such a test
        # harness eventually.

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_schedule_test(self):
        """Try to schedule a test. It doesn't have to run (but it can!) """

        slurm = schedulers.get_scheduler_plugin('slurm')

        cfg = TestConfigLoader().validate({
            'scheduler': 'slurm',
            'run': {
                'cmds': [
                    'echo "Hello World."'
                ]
            },
        })
        cfg['name'] = 'slurm_test'

        test = PavTest(self.pav_cfg, cfg, {})

        slurm.schedule_test(self.pav_cfg, test)

        status = slurm.job_status(self.pav_cfg, test)

        self.assertEqual(status.state, STATES.SCHEDULED)

        status = slurm.cancel_job(test)

        self.assertEqual(status.state, STATES.SCHED_CANCELLED)
