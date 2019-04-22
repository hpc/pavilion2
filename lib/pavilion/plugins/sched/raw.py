from pavilion import scriptcomposer
from pavilion.schedulers import SchedulerPlugin
from pavilion.schedulers import SchedulerPluginError
from pavilion.schedulers import SchedulerVariables
from pavilion.schedulers import dfr_sched_var
from pavilion.schedulers import sched_var
import os
import yaml_config as yc
import re
import subprocess


class RawVars(SchedulerVariables):
    pass

def slurm_float(val):
    if val == 'N/A':
        return None
    else:
        return float(val)


class Raw(SchedulerPlugin):

    VAR_CLASS = RawVars

    def __init__(self):
        super().__init__('raw')

    def get_conf(self):

        return yc.KeyedElem('raw', elements=[])
