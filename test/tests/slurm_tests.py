from pavilion import pav_test
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

    @unittest.skipIf(not has_slurm(), "Only runs on a system with slurm.")
    def test_vars(self):
        """Make sure all the slurm scheduler variable methods work when
        not on a node."""

        self.assertFalse(True)

