"""This module organizes the builtin scheduler plugins."""

from .base_classes import (SchedulerPlugin, SchedulerVariables, SchedulerPluginError,
                           var_method, dfr_var_method, get_plugin, list_plugins)

from .raw import Raw
from .slurm import Slurm
from .slurm_mpi import SlurmMPI

_builtin_scheduler_plugins = [
    Raw,
    Slurm,
    SlurmMPI,
]


def register_core_plugins():
    """Find and activate all builtin plugins."""

    for cls in _builtin_scheduler_plugins:
        obj = cls()
        obj.activate()


SchedulerPlugin.register_core_plugins = register_core_plugins
