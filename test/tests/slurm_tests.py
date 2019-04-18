from pavilion import config
from pavilion import plugins
from pavilion import schedulers
from pavilion.unittest import PavTestCase
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
    def test_slurm_vars(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        slurm = schedulers.get_scheduler_plugin('slurm')

        from pavilion.utils import cprint
        cprint(slurm.get_data()['summary'])

        # Grab a random jobid, and get the status of it.
        jobs = subprocess.check_output(['squeue', '-o', "%i %T"])
        jobs = jobs.decode('utf-8')
        last_job = jobs.strip().split('\n')[-1]
        jobid, status = last_job.strip().split()

        slurm.check_job(jobid)
