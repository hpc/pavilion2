"""This library manages the initialization of all the different Pavilion
plugin types. It also contains most of the included plugins themselves.

Plugin categories need to be registered in the 'PLUGIN_CATEGORIES' dictionary
for Pavilion to recognize them.

- Plugin base classes must all inherit from yapsy's IPlugin.IPlugin class
- Plugin base *modules* must contain a ``__reset()`` method that
  effectively ``deactivates()`` all plugins of that type.
- Plugin base *modules* **may** also contain a ``register_core_plugins()``
  to find, initialize, and ``activate()`` all plugins of that type
  that aren't included as separate yapsy plugin modules.
"""

import inspect
import logging
import traceback

from pavilion.commands import Command
from pavilion.errors import PluginError
from pavilion.expression_functions import FunctionPlugin
from pavilion.module_wrapper import ModuleWrapper
from pavilion.result_parsers import ResultParser
from pavilion.schedulers import SchedulerPlugin
from pavilion.sys_vars import SystemPlugin
from yapsy import PluginManager

LOGGER = logging.getLogger('plugins')

_PLUGIN_MANAGER = None

PLUGIN_CATEGORIES = {
    'command': Command,
    'function': FunctionPlugin,
    'module': ModuleWrapper,
    'result': ResultParser,
    'sched': SchedulerPlugin,
    'sys': SystemPlugin,
}

__all__ = [
    "initialize_plugins",
    "list_plugins",
]


def initialize_plugins(pav_cfg):
    """Initialize the plugin system, and activate plugins in all known plugin
    directories (except those specifically disabled in the config. Should
    only ever be run once pavilion command.
    :param pav_cfg: The pavilion configuration
    :return: Nothing
    :raises PluginError: When there's an issue with a plugin or the plugin
        system in general.
    :raises RuntimeError: When you try to run this twice.
    """

    global _PLUGIN_MANAGER  # pylint: disable=W0603

    if _PLUGIN_MANAGER is not None:
        LOGGER.warning("Tried to initialize plugins multiple times.")
        return

    plugin_dirs = []
    # Look in all the user provided plugin directories.
    for config in pav_cfg.configs.values():
        if (config['path']/'plugins').exists():
            plugin_dirs.append((config['path']/'plugins').as_posix())

    try:
        pman = PluginManager.PluginManager(directories_list=plugin_dirs,
                                           categories_filter=PLUGIN_CATEGORIES)

        pman.collectPlugins()
    except Exception as err:
        raise PluginError("Error initializing plugin system", err)

    # Activate each plugin in turn.
    for plugin in pman.getAllPlugins():
        plugin_dot_name = '{p.category}.{p.name}'.format(p=plugin)

        if plugin_dot_name in pav_cfg.disable_plugins:
            # Don't initialize these plugins.
            continue

        try:
            plugin.plugin_object.activate()
        except Exception as err:
            raise PluginError("Error activating plugin {name}"
                              .format(name=plugin.name),
                              prior_error=err, data=traceback.format_exc())

    # Some plugin types have core plugins that are built-in.
    for _, cat_obj in PLUGIN_CATEGORIES.items():
        if hasattr(cat_obj, 'register_core_plugins'):
            cat_obj.register_core_plugins()

    _PLUGIN_MANAGER = pman


def list_plugins():
    """Get the list of plugins by category. These will be IPlugin objects.
    :return: A dict of plugin categories, each with a dict of plugins by name.
    :raises RuntimeError: If you don't initialize the plugin system first
    """

    if _PLUGIN_MANAGER is None:
        raise RuntimeError("Plugin system has not been initialized.")

    plugins = {}
    for category in _PLUGIN_MANAGER.getCategories():
        plugins[category] = {}
        for plugin in _PLUGIN_MANAGER.getPluginsOfCategory(category):
            plugins[category][plugin.name] = plugin

    return plugins


def _reset_plugins():
    """Reset the plugin system. This functionality is for unittests,
    and should never be used in Pavilion proper."""

    global _PLUGIN_MANAGER  # pylint: disable=W0603

    _PLUGIN_MANAGER = None

    for _, cat_obj in PLUGIN_CATEGORIES.items():
        module = inspect.getmodule(cat_obj)

        if hasattr(module, '__reset'):
            module.__reset()  # pylint: disable=W0212
