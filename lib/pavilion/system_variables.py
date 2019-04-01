import collections
from pavilion.test_config import variables
from yapsy import IPlugin
import logging
import re
import inspect

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class SystemPluginError(RuntimeError):
    pass


_SYS_VAR_DICT = None
_LOADED_PLUGINS = None


class SysVarDict(collections.UserDict):

    def __init__(self, defer=False):
        global _SYS_VAR_DICT
        if _SYS_VAR_DICT is not None:
            raise SystemPluginError(
                     "Dictionary of system plugins can't be generated twice.")
        super().__init__({})
        _SYS_VAR_DICT = self

        self.defer = defer

    def __getitem__(self, name):
        """Return the corresponding item, if there's a system plugin for it."""

        global _LOADED_PLUGINS

        if name not in self.data:
            if name not in _LOADED_PLUGINS:
                raise KeyError("No system plugin named '{}'.".format(name))

            plugin = _LOADED_PLUGINS[name]

            self.data[name] = plugin.get(defer=self.defer)

        return self.data[name]


def __reset():
    global _SYS_VAR_DICT
    global _LOADED_PLUGINS

    _LOADED_PLUGINS = None
    _SYS_VAR_DICT = None


def get_system_plugin_dict(defer):
    """Get the dictionary of system plugins.
    :param bool defer: Whether the deferable plugins should be deferred.
    :rtype: dict
    """

    global _SYS_VAR_DICT

    if _SYS_VAR_DICT is None:
        return SysVarDict(defer=defer)
    else:
        return _SYS_VAR_DICT


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
            Note that deferable variables can't return a list.
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

    def _get(self):
        """This should be overridden to implement gathering of data for the
        system variable."""
        raise NotImplemented

    def get(self, defer):
        if defer and self.is_deferable:
            return variables.DeferredVariable(self.name, var_set='sys',
                                              sub_keys=self.sub_keys)
        elif defer and not self.is_deferable:
            raise SystemPluginError(
                "Deferred variable '{}' was requested but is not deferrable."
                .format(self.name)
            )
        elif self.values is None:
            self.values = {}
            if len(self.sub_keys) == 0:
                self.sub_keys = [None]
            for key in self.sub_keys:
                self.values[key] = None
            self._get()
            if list(self.values.keys()) == [None]:
                self.values = self.values[None]

        return self.values

    def activate(self):
        """Add this plugin to the system plugin list."""

        global _LOADED_PLUGINS

        name = self.name

        if _LOADED_PLUGINS is None:
            _LOADED_PLUGINS = {}

        if name not in _LOADED_PLUGINS:
            _LOADED_PLUGINS[name] = self
        elif self.priority > _LOADED_PLUGINS[name].priority:
            _LOADED_PLUGINS[name] = self
            LOGGER.warning("System plugin {} replaced due to priority."
                           .format(name))
        elif self.priority < _LOADED_PLUGINS[name].priority:
            LOGGER.warning("System plugin {} ignored due to priority."
                           .format(name))
        elif self.priority == _LOADED_PLUGINS[name].priority:
            from pavilion.utils import dprint
            dprint("is a b?", self is _LOADED_PLUGINS[name])
            raise SystemPluginError(
                "Two plugins for the same system plugin have "
                "the same priority {}, {} with name {}."
                .format(self, _LOADED_PLUGINS[name], name))

    def deactivate(self):
        """Remove this plugin from the system plugin list."""

        global _LOADED_PLUGINS

        if (self.name in _LOADED_PLUGINS and
                _LOADED_PLUGINS[self.name] is self):
            del _LOADED_PLUGINS[self.name]

            if (_SYS_VAR_DICT is not None and
                    self.name in _SYS_VAR_DICT):
                del _SYS_VAR_DICT[self.name]

    def __repr__(self):
        return '<{} from file {} named {}>'.format(
            self.__class__.__name__,
            inspect.getfile(self.__class__),
            self.name
        )
