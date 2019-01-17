import collections
from pavilion.variables import VariableSetManager
from yapsy.IPlugin import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))

class PluginSchedulerError(RuntimeError):
    pass

_SCHEDULER_PLUGINS = {}

class SchedVarDict( collections.UserDict ):

    def __init__( self ):
        global _SCHEDULER_PLUGINS
        super().__init__( _SCHEDULER_PLUGINS )

    def __getitem__( self, name ):
        plugin = self.data[ name ]
        return plugin.get()

def add_scheduler_plugin( scheduler_plugin ):
    global _SCHEDULER_PLUGINS
    name = scheduler_plugin.name

    if name not in _SCHEDULER_PLUGINS:
        _SCHEDULER_PLUGINS[ name ] = scheduler_plugin
    elif priority > _SCHEDULER_PLUGINS[name].priority:
        _SCHEDULER_PLUGINS[ name ] = scheduler_plugin
    elif priority == _SCHEDULER_PLUGINS[name].priority:
        raise PluginSchedulerError("Two plugins for the same system plugin "
                                "have the same priority {}, {}."
                                .format(scheduler_plugin,
                                        _SCHEDULER_PLUGINS[name]))

def remove_scheduler_plugin( scheduler_plugin ):
    global _SCHEDULER_PLUGINS
    name = scheduler_plugin.name

    if name in _SCHEDULER_PLUGINS:
        del _SCHEDULER_PLUGINS[ name ]

def get_scheduler_plugin( name ):
    global _SCHEDULER_PLUGINS
    if name not in _SCHEDULER_PLUGINS:
        raise PluginSchedulerError("Module not found: '{}'".format(name))

    return _SCHEDULER_PLUGINS[ name ]

class SchedulerPlugin(IPlugin):
