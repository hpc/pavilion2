"""Builtin system variable plugins and utilities. These are loaded manually for
speed."""

from . import base_classes
from .base_classes import SystemPlugin, SysVarDict, get_vars
from ..errors import SystemPluginError
from .host_cpus import HostCPUs
from .host_arch import HostArch
from .host_name import HostName
from .host_os import HostOS
from .sys_arch import SystemArch
from .sys_host import SystemHost
from .sys_name import SystemName
from .sys_os import SystemOS

_builtin_sys_plugins = [
    HostCPUs,
    HostArch,
    HostName,
    HostOS,
    SystemArch,
    SystemName,
    SystemOS,
    SystemHost
]


def register_core_plugins():
    """Add all builtin plugins and activate them."""

    for cls in _builtin_sys_plugins:
        obj = cls()
        obj.activate()


SystemPlugin.register_core_plugins = register_core_plugins
