import collections
from pavilion import variables
from yapsy import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))

class SystemPluginError(RuntimeError):
    pass

_SYSTEM_PLUGINS = None

_LOADED_PLUGINS = None

class SysVarDict( collections.UserDict ):

    def __init__( self, defer=None ):
        global _SYSTEM_PLUGINS
        if _SYSTEM_PLUGINS is not None:
            raise SystemPluginError(
                     "Dictionary of system plugins can't be generated twice." )
        super().__init__( {} )
        _SYSTEM_PLUGINS = self

        if defer is None:
            defer = False # default

        self.defer = defer

    def set_defer( self, defer ):
        self.defer = defer

    def __getitem__( self, name ):
        if name not in self.data:
            self.data[ name ] = \
                              get_system_plugin( name ).get( defer=self.defer )
        return self.data[ name ]

    def _reset( self ):
        LOGGER.warning( "Resetting the plugins.  This functionality exists " +\
               "only for use by unittests." )
        _reset_plugins()
        self.data = {}

def _reset_plugins():
    global _SYSTEM_PLUGINS

    if _SYSTEM_PLUGINS is not None:
        for key in list(_SYSTEM_PLUGINS.keys()):
            remove_system_plugin( key )

def add_system_plugin( system_plugin ):
    global _LOADED_PLUGINS

    name = system_plugin.name

    if _LOADED_PLUGINS is None:
        _LOADED_PLUGINS = {}

    if name not in _LOADED_PLUGINS:
        _LOADED_PLUGINS[ name ] = system_plugin
    elif system_plugin.priority > _LOADED_PLUGINS[ name ].priority:
        _LOADED_PLUGINS[ name ] = system_plugin
        LOGGER.warning( "System plugin {} ignored due to priority.".format(
                        name ) )
    elif system_plugin.priority == _LOADED_PLUGINS[name].priority:
        raise SystemPluginError("Two plugins for the same system plugin have "
                                "the same priority {}, {} with name {}."
                                .format(system_plugin, _LOADED_PLUGINS[name],
                                        name))

def remove_system_plugin( plugin_name ):
    global _SYSTEM_PLUGINS

    if plugin_name in _SYSTEM_PLUGINS:
        del _SYSTEM_PLUGINS[ plugin_name ]

def get_system_plugin( name ):
    global _LOADED_PLUGINS

    if _LOADED_PLUGINS is None:
        raise SystemPluginError(
                              "Trying to get plugins before they are loaded." )

    if name not in _LOADED_PLUGINS:
        raise SystemPluginError("Module not found: '{}'".format(name))

    return _LOADED_PLUGINS[ name ]

class SystemPlugin(IPlugin.IPlugin):

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

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
            raise SystemPluginError("Invalid module name: '{}'".format(
                                                                  plugin_name))

        self.name = plugin_name
        self.priority = priority
        if sub_keys is None:
            sub_keys = []
        self.sub_keys = sub_keys
        self.values = None

    def __reset( self ):
        self.values = None

    def _get( self ):
        raise NotImplemented

    def get( self, defer ):
        if defer and self.is_deferable:
            return variables.DeferredVariable(self.name, var_set='sys',
                                              sub_keys=self.sub_keys,
                                              priority=self.priority)
        elif defer and not self.is_deferable:
            raise SystemPluginError("Deferred variable '{}'".format(self.name)+
                                    " was requested but is not deferrable.")
        elif self.values is None:
            self.values = {}
            if len(self.sub_keys) == 0:
                self.sub_keys = [ None ]
            for key in self.sub_keys:
                self.values[ key ] = None
            self._get()
            if list(self.values.keys()) == [ None ]:
                self.values = self.values[ None ]

        return self.values

    def activate(self):
        """Add this plugin to the system plugin list."""

        add_system_plugin( self )

    def deactivate(self):
        """Remove this plugin from the system plugin list."""

        remove_system_plugin( self )

    def __reset():
        """Remove this plugin and its changes."""

        self.deactivate()
