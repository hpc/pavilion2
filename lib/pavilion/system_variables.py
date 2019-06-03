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
_LOADED_PLUGINS = None  # type : dict


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

    @classmethod
    def get_obj(cls, name):
        """Return the corresponding object without invoking the .get method."""

        global _LOADED_PLUGINS

        if name not in _LOADED_PLUGINS:
            raise KeyError("No system plugin named '{}'.".format(name))

        return _LOADED_PLUGINS[name]

    def keys(self):

        global _LOADED_PLUGINS

        return _LOADED_PLUGINS.keys()

    def items(self):
        return [(key, self[key]) for key in self.keys()]

    def values(self):
        return [self[key] for key in self.keys()]

    def __iter__(self):
        return self.keys()

    @staticmethod
    def help(key):
        """Return help information for the given key."""

        global _LOADED_PLUGINS

        return _LOADED_PLUGINS[key].help_text


def __reset():
    global _SYS_VAR_DICT
    global _LOADED_PLUGINS

    _LOADED_PLUGINS = None
    _SYS_VAR_DICT = None


def get_vars(defer):
    """Get the dictionary of system plugins.
    :param bool defer: Whether the deferable plugins should be deferred.
    :rtype: SysVarDict
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

    def __init__(self,
                 plugin_name,
                 help_text,
                 priority=PRIO_DEFAULT,
                 is_deferable=False,
                 sub_keys=None):
        """Initialize the system plugin instance.  This should be overridden in
        each final plugin.
        :param str plugin_name: The name of the system plugin being wrapped.
        :param str help_text: Short description of this value.
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

        self.help_text = help_text
        self.name = plugin_name
        self.priority = priority
        self.path = inspect.getfile(self.__class__)
        if sub_keys is None:
            sub_keys = []
        self.sub_keys = sub_keys
        self.values = None

    def _get(self):
        """This should be overridden to implement gathering of data for the
        system variable."""
        raise NotImplementedError

    def get(self, defer):
        if defer and self.is_deferable:
            return variables.DeferredVariable(self.name, var_set='sys',
                                              sub_keys=self.sub_keys)

        if self.values is None:
            self.values = self._get()

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
                           .format(self.path))
        elif self.priority == _LOADED_PLUGINS[name].priority:
            raise SystemPluginError(
                "Two plugins for the same system plugin have "
                "the same priority: \n{} and \n{}."
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
        return '<{} from file {} named {}, priority {}>'.format(
            self.__class__.__name__,
            self.path,
            self.name,
            self.priority
        )
