"""This module organizes the builtin scheduler plugins."""

from .scheduler import (SchedulerPlugin, SchedulerPluginError,
                        get_plugin, list_plugins)
from .vars import SchedulerVariables

from pavilion.schedulers.plugins.raw import Raw
from pavilion.schedulers.plugins.slurm import Slurm
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
