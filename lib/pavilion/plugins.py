from yapsy.PluginManager import PluginManager
from pavilion.module_wrapper import ModuleWrapper
import os

_INIT_DONE=False

_PLUGIN_MANAGER=None


class PluginError(RuntimeError):
    pass


def initialize_plugins(pav_cfg):
    """Initialize the plugin system, and activate plugins in all known plugin directories (except
    those specifically disabled in the config. Should only ever be run once pavilion command.
    :param pav_cfg: The pavilion configuration
    :return: Nothing
    :raises PluginError: When there's an issue with a plugin or the plugin system in general.
    :raises RuntimeError: When you try to run this twice.
    """

    global _PLUGIN_MANAGER

    if _PLUGIN_MANAGER is not None:
        raise RuntimeError("Plugins should only be initialized once per run of Pavilion.")

    plugin_dirs = [os.path.join(cfg_dir, 'plugins') for cfg_dir in pav_cfg.config_dirs]

    categories = {
        'module': ModuleWrapper,
        # sys plugins
        # cmd plugins
        # scheduler plugins
    }

    try:
        pman = PluginManager(directories_list=plugin_dirs,
                             categories_filter=categories)

        pman.locatePlugins()
        pman.collectPlugins()
    except Exception as err:
        raise PluginError("Error initializing plugin system: {}".format(err))

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
