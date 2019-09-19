from pavilion import scriptcomposer
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerPluginError
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import dfr_var_method
from pavilion.var_dict import var_method
from pavilion.status_file import STATES, StatusInfo
import os
import yaml_config as yc
import re
import subprocess
from pathlib import Path

import pavilion.plugins.sched.slurm as slurm


class SlurmMPIVars(slurm.SlurmVars):

    @dfr_var_method
    def test_cmd(self):
        """Same variables as Slurm scheduler plugin, only it uses
        mpirun and not srun"""
        return 'mpirun'


class SlurmMPI(slurm.Slurm):

    VAR_CLASS = SlurmMPIVars

    def __init__(self):
        SchedulerPlugin.__init__(
            self,
            'slurm_mpi',
            'mpirun',
            priority=10
        )

