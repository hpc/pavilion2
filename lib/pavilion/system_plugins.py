import collections
from pavilion.variables import VariableSetManager
from yapsy.IPlugin import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))

class PluginSystemError(RuntimeError):
    pass

_SYSTEM_PLUGINS = {}

class SysVarDict( collections.UserDict ):

    def __init__( self, want_deferred=True ):
        global._SYSTEM_PLUGINS
        super().__init__(_SYSTEM_PLUGINS)
        self.want_deferred = want_deferred

    def __getitem__( self, name ):
        plugin = self.data[ name ]
        return plugin.get()

def add_system_plugin( system_plugin ):
    name = system_plugin.name

    if name not in _SYSTEM_PLUGINS:
        _SYSTEM_PLUGINS[ name ] = system_plugin
    elif priority > _SYSTEM_PLUGINS[name].priority:
        _SYSTEM_PLUGINS[ name ] = system_plugin
    elif priority == _SYSTEM_PLUGINS[name].priority:
        raise PluginSystemError("Two plugins for the same system plugin have "
                                "the same priority {}, {}."
                                .format(system_plugin, _SYSTEM_PLUGINS[name]))

def remove_system_plugin( system_plugin ):
    name = system_plugin.name

    if name in _SYSTEM_PLUGINS:
        del _SYSTEM_PLUGINS[ name ]

def get_system_plugin( name ):
    if name not in _SYSTEM_PLUGINS:
        raise PluginSystemError("Module not found: '{}'".format(name))

    return _SYSTEM_PLUGINS[ name ]

class SystemPlugin(IPlugin):

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20
    global._SYSTEM_PLUGINS

    def __init__(self, plugin_name, priority=PRIO_DEFAULT, is_deferable=False,
                 sub_keys=[ None ]):
        """Initialize the system plugin instance.  This should be overridden in
        each final plugin.
        :param str plugin_name: The name of the system plugin being wrapped.
        :param int priority: Priority value of plugin when two plugins have
                             the same name.
        :param bool is_deferable: Whether the plugin is able to be deferred.
        :param str/dict sub_keys: Key or list of keys used with this plugin.
        """
        super().__init__()

        self.is_deferable = is_deferable

        if self.NAME_VERS_RE.match(name) is None:
            raise PluginSystemError("Invalid module name: '{}'".format(name))

        self.name = plugin_name
        self.priority = priority
        self.sub_keys = sub_keys
        self.values = {}

        _SYSTEM_PLUGINS[ self.name ] = {}

        for key in self.sub_keys:
            _SYSTEM_PLUGINS[ self.name ][ key ] = None
            self.values[ key ] = None

    def _get( self, sub_key=None ):
        raise NotImplemented

    def get( self, sub_key=None, defer=True )
        if defer and self.is_deferable:
            return variables.DeferredVariable(self.name, 'sys', self.sub_keys)
        elif defer and not self.is_deferable:
            raise PluginSystemError("Deferred variable '{}'".format(self.name)+
                                    " was requested but is not deferrable.")
        elif _SYSTEM_PLUGINS[ self.name ][ sub_key ] is None:
            _SYSTEM_PLUGINS[ self.name ][ sub_key ] = self._get( sub_key )

        return _SYSTEM_PLUGINS[self.name][ sub_key ]

    def activate(self):
        """Add this plugin to the system plugin list."""

        add_system_plugin( self )

    def deactivate(self):
        """Remove this plugin from the system plugin list."""

        remove_system_plugin( self )
