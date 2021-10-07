"""System Variables provide a way for pavilion users to add additional
variables for Pavilion tests to use. In particular, these are useful
for gathering site-specific information for your tests."""

# pylint: disable=W0603

import collections
import inspect
import logging
import re

from pavilion.test_config import variables
from yapsy import IPlugin

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class SystemPluginError(RuntimeError):
    """Error thrown when a system plugin encounters an error."""


_SYS_VAR_DICT = None
_LOADED_PLUGINS = None  # type : dict


class SysVarDict(collections.UserDict):
    """This dictionary based object provides lazy, cached lookups of
all system variable values according to what system variable plugins
are actually loaded.  The values, once retrieved, are thus static
for a given run of the pavilion command."""

    def __init__(self, defer=False, unique=False):
        """Create a new system variable dictionary. Typically the first one
        created is reused for the entire run of Pavilion.
        :param bool defer: Whether to defer deferrable variables.
        :param bool unique: Usually, creating more than one of these is an
            error. Ignore that if this is true. (For testing).
        """

        super().__init__({})

        if not unique:
            global _SYS_VAR_DICT
            if _SYS_VAR_DICT is not None:
                raise SystemPluginError(
                    "Dictionary of system plugins can't be generated twice.")
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
        """As per dict.keys() (except we're really listing the loaded
plugins.)"""

        global _LOADED_PLUGINS

        return _LOADED_PLUGINS.keys()

    def items(self):
        """As per dict.items()"""
        return [(key, self[key]) for key in self.keys()]

    def values(self):
        """As per dict.values()"""
        return [self[key] for key in self.keys()]

    def __iter__(self):
        return iter(self.keys())

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
    """Each system variable plugin provides a key and value for the system
    variables dictionary. These are only evaluated if asked for,
    and generally only once."""

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self,
                 name,
                 description,
                 priority=PRIO_COMMON,
                 is_deferable=False,
                 sub_keys=None):
        """Initialize the system plugin instance.  This should be overridden in
        each final plugin.

        :param str name: The name of the system plugin being wrapped.
        :param str description: Short description of this value.
        :param int priority: Priority value of plugin when two plugins have
            the same name.
        :param bool is_deferable: Whether the plugin is able to be deferred.
            Note that deferable variables can't return a list.
        :param Union(str,dict) sub_keys: Deprecated (unused). You no longer
            need to define the sub_keys in advance.
        """
        super().__init__()

        self.is_deferable = is_deferable

        if self.NAME_VERS_RE.match(name) is None:
            raise SystemPluginError(
                "Invalid module name: '{}'"
                .format(name))

        self.help_text = description
        self.name = name
        self.priority = priority
        self.path = inspect.getfile(self.__class__)

    def _get(self):
        """This should be overridden to implement gathering of data for the
        system variable.
        """
        raise NotImplementedError

    def get(self, defer):
        """Get the value for this system variable.

        :params bool defer: If the variable is deferable, return a
            DeferredVariable object instead.
        """
        if defer and self.is_deferable:
            return variables.DeferredVariable()

        try:
            values = self._get()
        except Exception as err:
            raise SystemPluginError(
                "Error getting value for system plugin {s.name}: {err}"
                .format(s=self, err=err)
            )

        chk_vals = values
        if not isinstance(chk_vals, list):
            chk_vals = [chk_vals]

        for i in range(len(chk_vals)):
            if not isinstance(chk_vals[i], dict):
                chk_vals[i] = {None: chk_vals[i]}

        for vals in chk_vals:
            for key, val in vals.items():
                if not isinstance(val, str):
                    raise SystemPluginError(
                        "System variable plugin {s.path} called {s.name} "
                        "returned non-string value '{val}' in '{values}'"
                        .format(s=self, val=val, values=values))

        return values

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
            LOGGER.warning("System plugin %s replaced due to priority.", name)
        elif self.priority < _LOADED_PLUGINS[name].priority:
            LOGGER.warning("System plugin %s ignored due to priority.",
                           self.path)
        elif self.priority == _LOADED_PLUGINS[name].priority:
            raise SystemPluginError(
                "Two plugins for the same system plugin have "
                "the same priority: \n{} and \n{}."
                .format(_LOADED_PLUGINS[name], name))

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
