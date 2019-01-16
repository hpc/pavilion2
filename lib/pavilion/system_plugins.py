import collections
from pavilion import variables
from yapsy import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))

class PluginSystemError(RuntimeError):
    pass

_SYSTEM_PLUGINS = None

class SysVarDict( collections.UserDict ):

    def __init__( self ):
        global _SYSTEM_PLUGINS
        if _SYSTEM_PLUGINS is not None:
            raise PluginSystemError(
                     "Dictionary of system plugins can't be generated twice." )
        super().__init__( {} )
        _SYSTEM_PLUGINS = self

        self.defer = False # Default

    def set_defer( self, defer=True ):
        self.defer = defer

    def get_object( self, name ):
        return get_system_plugin( name )

    def __getitem__( self, name ):
        plugin = get_system_plugin( name )
        return plugin.get( defer=self.defer )

def add_system_plugin( system_plugin ):
    name = system_plugin.name

    if name not in _SYSTEM_PLUGINS:
        _SYSTEM_PLUGINS[ name ] = system_plugin
    elif isinstance(get_system_plugin( name ), variables.DeferredVariable ) \
         and not system_plugin.is_deferable:
        raise PluginSystemError("Two plugins of the same name don't have " + \
                                "the same deferability.")
    elif system_plugin.priority > get_system_plugin( name ).priority:
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

class SystemPlugin(IPlugin.IPlugin):

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    global _SYSTEM_PLUGINS

    def __init__(self, plugin_name, priority=PRIO_DEFAULT, is_deferable=False,
                 sub_keys=None):
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

        if self.NAME_VERS_RE.match(plugin_name) is None:
            raise PluginSystemError("Invalid module name: '{}'".format(
                                                                  plugin_name))

        if _SYSTEM_PLUGINS is None:
            SysVarDict()

        self.name = plugin_name
        self.priority = priority
        if sub_keys is None:
            sub_keys = []
        self.sub_keys = sub_keys
        self.values = None

        _SYSTEM_PLUGINS[ plugin_name ] = self

    def _get( self ):
        raise NotImplemented

    def get( self, defer=True ):
        if defer and self.is_deferable:
            return variables.DeferredVariable(self.name, var_set='sys',
                                              sub_keys=self.sub_keys,
                                              priority=self.priority)
        elif defer and not self.is_deferable:
            raise PluginSystemError("Deferred variable '{}'".format(self.name)+
                                    " was requested but is not deferrable.")
        elif self.values is None:
            self._get()

        return self.values

    def activate(self, ):
        """Add this plugin to the system plugin list."""

        add_system_plugin( self )

    def deactivate(self):
        """Remove this plugin from the system plugin list."""

        remove_system_plugin( self )

    def __reset():
        """Remove this plugin and its changes."""

        self.deactivate()
