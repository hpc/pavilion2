"""This module organizes the builtin scheduler plugins."""
from typing import Union

from .plugins.raw import Raw
from .plugins.slurm import Slurm
from .advanced import SchedulerPluginAdvanced
from .basic import SchedulerPluginBasic
from .config import validate_config
from .scheduler import (SchedulerPluginError, SchedulerPlugin, KickoffScriptHeader,
                        _SCHEDULER_PLUGINS)
from ..types import NodeInfo, Nodes, NodeList, NodeSet
from .vars import SchedulerVariables

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


def get_plugin(name) -> Union[SchedulerPluginBasic,
                              SchedulerPluginAdvanced]:
    """Return a scheduler plugin

    :param str name: The name of the scheduler plugin.
    """

    if _SCHEDULER_PLUGINS is None:
        raise SchedulerPluginError("No scheduler plugins loaded.")

    if name not in _SCHEDULER_PLUGINS:
        raise SchedulerPluginError(
            "Scheduler plugin not found: '{}'".format(name))

    return _SCHEDULER_PLUGINS[name]


def list_plugins():
    """Return a list of all available scheduler plugin names.

    :rtype: list
    """
    if _SCHEDULER_PLUGINS is None:
        raise SchedulerPluginError("Scheduler Plugins aren't loaded.")

    return list(_SCHEDULER_PLUGINS.keys())
