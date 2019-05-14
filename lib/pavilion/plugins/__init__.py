from pathlib import Path
from pavilion.commands import Command
from pavilion.module_wrapper import ModuleWrapper
from pavilion.result_parsers import ResultParser
from pavilion.schedulers import SchedulerPlugin
from pavilion.system_variables import SystemPlugin as System
from yapsy import PluginManager
import logging

LOGGER = logging.getLogger('plugins')

_PLUGIN_MANAGER = None

PLUGIN_CATEGORIES = {
    'module': ModuleWrapper,
    'command': Command,
    'sys': System,
    'sched': SchedulerPlugin,
    'result': ResultParser,
}

__all__ = [
    "PluginError",
    "initialize_plugins",
    "list_plugins",
]


class PluginError(RuntimeError):
    pass


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

    global _PLUGIN_MANAGER

    if _PLUGIN_MANAGER is not None:
        LOGGER.warning("Tried to initialize plugins multiple times.")
        return

    plugin_dirs = [str(Path(cfg_dir)/'plugins')
                   for cfg_dir in pav_cfg.config_dirs]

    try:
        pman = PluginManager.PluginManager(directories_list=plugin_dirs,
                                           categories_filter=PLUGIN_CATEGORIES)

        pman.locatePlugins()
        pman.collectPlugins()
    except Exception as err:
        raise PluginError("Error initializing plugin system: {}".format(err))

    disable_plugins = pav_cfg.disable_plugins

    for plugin in pman.getAllPlugins():
        plugin_dot_name = '{p.category}.{p.name}'.format(p=plugin)

        if plugin_dot_name in pav_cfg.disable_plugins:
            # Don't initialize these plugins.
            continue

        try:
            pman.activatePluginByName(plugin.name, plugin.category)
        except Exception as err:
            raise PluginError("Error activating plugin {name}: {err}"
                              .format(name=plugin.name, err=err))

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
    LOGGER.warning("Resetting the plugins. This functionality exists only for "
                   "use by unittests.")
    import inspect

    global _PLUGIN_MANAGER

    _PLUGIN_MANAGER = None

    for cat, cat_obj in PLUGIN_CATEGORIES.items():
        module = inspect.getmodule(cat_obj)

        if hasattr(module, '__reset'):
            module.__reset()
