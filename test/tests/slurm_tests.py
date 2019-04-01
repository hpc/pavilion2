from pavilion import plugins
from pavilion import config
from pavilion import schedulers
import datetime
import os
import subprocess
import tempfile
import time
import unittest
import tzlocal


_HAS_SLURM = None


def has_slurm():
    global _HAS_SLURM
    if _HAS_SLURM is None:
        try:
            _HAS_SLURM = subprocess.call(['sinfo', '--version']) == 0
        except (FileNotFoundError, subprocess.CalledProcessError):
            _HAS_SLURM = False

    return _HAS_SLURM


class SlurmTests(unittest.TestCase):

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
    def test_vars(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        schedulers.get_scheduler_plugin('slurm')