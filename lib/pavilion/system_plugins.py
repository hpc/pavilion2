from yapsy.IPlugin import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))

class PluginSystemError(RuntimeError):
    pass

_SYSTEM_PLUGINS = {}

def add_system_plugin( system_plugin ):
    name = system_plugin.name

    if name not in _SYSTEM_PLUGINS:
        _SYSTEM_PLUGINS[ name ] = system_plugin

def remove_system_plugin( system_plugin ):
    name = system_plugin.name

    if name in _SYSTEM_PLUGINS:
        del _SYSTEM_PLUGINS[ name ]

def get_system_plugin( name ):
    if name not in _SYSTEM_PLUGINS:
        raise PluginSystemError("Module not found: '{}'".format(name))

    return _SYSTEM_PLUGINS[ name ]

class SystemPlugin(IPlugin):

    def __init__(self, plugin_name):
        """Initialize the system plugin instance.  This should be overridden in
        each final plugin.
        :param str name: The name of the system plugin being wrapped.
        """

        super().__init__()

        if self.NAME_VERS_RE.match(name) is None:
            raise PluginSystemError("Invalid module name: '{}'".format(name))

        self.name = name

    def get():
        raise NotImplemented

    def activate(self):
        """Add this plugin to the system plugin list."""

        add_system_plugin( self )

    def deactivate(self):
        """Remove this plugin from the system plugin list."""

        remove_system_plugin( self )
