"""This module organizes the builtin scheduler plugins."""

from .scheduler import (SchedulerPluginError, SchedulerPluginAdvanced,
                        SchedulerPlugin, KickoffScriptHeader,
                        SchedulerPluginBasic, get_plugin, list_plugins)
from .vars import SchedulerVariables
from .types import NodeList, NodeSet, Nodes, NodeInfo
from .config import validate_config

from pavilion.schedulers.plugins.raw import Raw
from pavilion.schedulers.plugins.slurm import Slurm

_builtin_scheduler_plugins = [
    Raw,
    Slurm,
]


def register_core_plugins():
    """Find and activate all builtin plugins."""

    for cls in _builtin_scheduler_plugins:
        obj = cls()
        obj.activate()


SchedulerPlugin.register_core_plugins = register_core_plugins
