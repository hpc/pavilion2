"""Plugin system for altering module behavior."""
import collections
import inspect
import logging
import re
from typing import List, Union, Dict

from pavilion.module_actions import (
    ModuleLoad, ModuleSwap, ModuleUnload, ModuleAction)
from pavilion.variables import VariableSetManager
from yapsy import IPlugin

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class ModuleWrapperError(RuntimeError):
    """Raised when any module wrapping related errors occur."""


_WRAPPED_MODULES = {}


def __reset():
    global _WRAPPED_MODULES  # pylint: disable=W0603

    _WRAPPED_MODULES = {}


def add_wrapped_module(module_wrapper, version):
    """Add the module wrapper to the set of wrapped modules.

:param ModuleWrapper module_wrapper: The module_wrapper class for the
                                     module.
:param Union(str, None) version: The version to add it under.
:return: None
:raises KeyError: On module version conflict.
"""

    name = module_wrapper.name
    priority = module_wrapper.priority

    if name not in _WRAPPED_MODULES:
        _WRAPPED_MODULES[name] = {version: module_wrapper}
    elif version not in _WRAPPED_MODULES[name]:
        _WRAPPED_MODULES[name][version] = module_wrapper
    elif priority > _WRAPPED_MODULES[name][version].priority:
        _WRAPPED_MODULES[name][version] = module_wrapper
    elif priority == _WRAPPED_MODULES[name][version].priority:
        raise ModuleWrapperError(
            "Two modules for the same module/version, with the same "
            "priority {}, {}."
            .format(module_wrapper.path,
                    _WRAPPED_MODULES[name][version].path))


def remove_wrapped_module(module_wrapper, version):
    """Remove the indicated module_wrapper from the set of wrapped module.

:param ModuleWrapper module_wrapper: The module_wrapper to remove,
                                     if it exists.
:param Union(str, None) version: The specific version to remove.
:returns: None
"""

    name = module_wrapper.name

    if name in _WRAPPED_MODULES and version in _WRAPPED_MODULES[name]:
        del _WRAPPED_MODULES[name][version]

        if not _WRAPPED_MODULES[name]:
            del _WRAPPED_MODULES[name]


def get_module_wrapper(name, version: Union[None, str] = None,
                       config_wrappers: Union[Dict[str, dict], None] = None) \
        -> "ModuleWrapper":
    """Finds and returns a module wrapper to match the specified module
    name and version. The default module wrapper is returned if a match isn't
    found.

    :param name: The name of the module.
    :param version: The version requested. If None is specified this will look for the
        version-generic module wrapper for this module.
    :param config_wrappers: The module wrappers defined via test config.
"""

    config_wrappers = config_wrappers or {}

    if name in _WRAPPED_MODULES:
        if version in _WRAPPED_MODULES[name]:
            # Grab the version specific wrapper.
            return _WRAPPED_MODULES[name][version]
        elif None in _WRAPPED_MODULES[name]:
            # Grab the generic wrapper for this module
            return _WRAPPED_MODULES[name][None]

    for wr_name, wr_config in config_wrappers.items():
        _, (mod_name, mod_vers), _ = parse_module(wr_name)

        if name == mod_name:
            if mod_vers == version or mod_vers is None:
                return ModuleWrapperViaConfig(name=mod_name, version=mod_vers, config=wr_config)

    return ModuleWrapper(name, '<default>', version=version)


def list_module_wrappers():
    """Returns a list of all loaded module wrapper plugins.

:rtype: list
"""
    return list(_WRAPPED_MODULES.keys())


ACTION_LOAD = 'load'
ACTION_SWAP = 'swap'
ACTION_UNLOAD = 'unload'


def parse_module(mod_line):
    """Parse a module specification into it's components. These can come
    in one of three formats:

    1. 'mod-name[/version]' - Load the given module name and version
    2. '-mod-name[/version]' - Unload the given module/version.
    3. 'old_name[/old_vers]->mod-name[/version]' - Swap the given old
       module for the new one.

    :param str mod_line: String provided by the user in the config.
    :rtype: (str, (str, str), (str, str))
    :return: action, (name, vers), (old_name, old_vers)
    """

    old_mod = None
    if '->' in mod_line:
        old_mod, mod = mod_line.split('->')
        action = ACTION_SWAP
    elif mod_line.startswith('-'):
        action = ACTION_UNLOAD
        mod = mod_line[1:]
    else:
        action = ACTION_LOAD
        mod = mod_line

    if '/' in mod:
        mod_name, mod_vers = mod.rsplit('/', 1)
    else:
        mod_name = mod
        mod_vers = None

    if old_mod is not None:
        if '/' in old_mod:
            old_mod_name, old_mod_vers = old_mod.rsplit('/', 1)
        else:
            old_mod_name = old_mod
            old_mod_vers = None

        return action, (mod_name, mod_vers), (old_mod_name, old_mod_vers)
    else:
        return action, (mod_name, mod_vers), (None, None)


class ModuleWrapper(IPlugin.IPlugin):
    """The base class for all module wrapper plugins."""

    LMOD = 'lmod'
    EMOD = 'emod'
    NONE = 'none'

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+(/[a-zA-Z0-9_.-]+)*$')

    def __init__(self, name, description, version=None, priority=PRIO_COMMON):
        """Initialize the module wrapper instance. This must be overridden in
plugin as the plugin system can't handle the arguments

:param str name: The name of the module being wrapped.
:param str description: A description of this wrapper.
:param str version: The version of module file to wrap. None denotes a
                    wild version or a version-less modulefile.
:param int priority: The priority of this wrapper. It will replace
                     identical wrappers of a lower priority when loaded. Use
                     the ModuleWrapper.PRIO_* constants.
"""

        super().__init__()

        if self.NAME_VERS_RE.match(name) is None:
            raise ModuleWrapperError("Invalid module name: '{}'".format(name))
        if version is not None and self.NAME_VERS_RE.match(version) is None:
            raise ModuleWrapperError(
                "Invalid module version: '{}'".format(name))

        self.name = name
        self._version = version
        self.help_text = description
        self.priority = priority

    def get_version(self, requested_version):
        """Get the version of the module to load, given the requested
version and the version set in the instance. This should always be
used to figure out what version to load.

:param Union(str, None) requested_version: The version requested by
 the user.
:rtype: str
:return: The version that should be loaded.
"""

        if self._version is not None and requested_version != self._version:
            raise ModuleWrapperError(
                "Version mismatch. A module wrapper specifically for "
                "version '{s._version}' of '{s.name}' was used with "
                "a non-matching requested version '{requested}'."
                .format(s=self, requested=requested_version))

        return requested_version

    @property
    def path(self):
        """The location of this module wrapper plugin."""

        return inspect.getfile(self.__class__)

    def activate(self):
        """Add this module to the wrapped module list."""

        add_wrapped_module(self, self._version)

    def deactivate(self):
        """Remove this module from the wrapped module list."""

        remove_wrapped_module(self, self._version)

    def load(self, var_man: VariableSetManager,
             requested_version=None) \
            -> (List[Union[ModuleAction, str]], dict):
        """Generate the list of module actions and environment changes to load
this module.

:param VariableSetManager var_man: The test's variable manager. al
:param str requested_version: The version requested to load.
:return: A list of actions (or bash command strings), and a dict of
         environment changes.
:rtype: (Union(str, ModuleAction), dict)
:raises ModuleWrapperError: If the requested version does not work with
                            this instance.
"""

        return self._load(var_man, self.get_version(requested_version))

    def _load(self, var_man: VariableSetManager, version: str) \
            -> (List[Union[ModuleAction, str]], dict):
        """Override this to change how the module is loaded.
        :param VariableSetManager var_man: The variable set manager. Use
            to get Pavilion variable values. (``var_man['sys.sys_name']``)
        :param str version:
        :return: This returns a list of module actions/strings and a
        dictionary of environment changes.  The module actions and strings
        will become lines written to run or build scripts. The dictionary of
        environment changes will result in those variables being exported. If
        order is important, use a collections.OrderedDict.
        """

        _ = var_man

        return [ModuleLoad(self.name, version)], {}

    def swap(self, var_man, out_name, out_version, requested_version=None) \
            -> (List[Union[ModuleAction, str]], dict):
        """Swap out the 'out' module and swap in the new module.

    :param var_man: The test's variable manager. Module wrappers can use this
        to lookup any non-deferred test variable.
    :param str out_name: The name of the module to swap out.
    :param str out_version: The version of the module to swap out.
    :param str requested_version: The version requested to load.
    :return: A list of actions (or bash command strings), and a dict of
             environment changes.
    :rtype: (Union(str, ModuleAction), dict)
    :raises ModuleWrapperError: If the requested version does not work
                                with this instance.
    """
        version = self.get_version(requested_version)

        return self._swap(var_man, out_name, out_version, version)

    def _swap(self, var_man: VariableSetManager, out_name: str,
              out_version: str, version: str) \
            -> (List[Union[ModuleAction, str]], dict):
        """Override to change how this module is loaded.

        :param var_man: The variable set manager.
        :param out_name: The name of the module to swap out.
        :param out_version: The module version to swap out. May be None.
        :param version: The version to swap in.
        :return: A per _load()"""

        _ = var_man

        return [ModuleSwap(self.name, version, out_name, out_version)], {}

    def unload(self, var_man, requested_version=None):
        """Remove this module from the environment.

    :param var_man: The test's variable manager. Module wrappers can use this
        to lookup any non-deferred test variable.
    :param str requested_version: The version requested to remove.
    :return: A list of actions (or bash command strings), and a dict of
             environment changes.
    :rtype: (Union(str, ModuleAction), dict)
    :raises ModuleWrapperError: If the requested version does not work with
                                this instance.
    """

        version = self.get_version(requested_version)

        return self._unload(var_man, version)

    def _unload(self, var_man, version):
        """Override this to change how this module is unloaded.

        :param var_man:
        :param version:
        :return:
        """

        _ = var_man

        return [ModuleUnload(self.name, version)], {}


class ModuleWrapperViaConfig(ModuleWrapper):
    """A dynamic module wrapper based on one defined in the test config."""

    def __init__(self, name: str, version: Union[None, str], config: Dict[str, dict]):

        super().__init__(name,
                         '{} module wrapper via config.'.format(name),
                         version=version)

        self.modules = config.get('modules', [])
        self.env = config.get('env', {})

    def _load(self, var_man: VariableSetManager, version: str) \
            -> (List[Union[ModuleAction, str]], dict):

        actions = []
        for load_action in self.modules:
            action, (mod_name, mod_vers), (old_mod_name, old_mod_vers) = parse_module(load_action)

            if mod_name == self.name and not mod_vers:
                mod_vers = version

            if action == ACTION_UNLOAD:
                actions.append(ModuleUnload(mod_name, mod_vers))
            elif action == ACTION_SWAP:
                actions.append(ModuleSwap(
                    module_name=mod_name,
                    version=mod_vers,
                    old_module_name=old_mod_name,
                    old_version=old_mod_vers,
                ))
            else:
                actions.append(ModuleLoad(module_name=mod_name, version=mod_vers))

        env_vars = collections.OrderedDict()
        if version:
            vers_var_name = '{}_VERSION'.format(self.name)
            env_vars[vers_var_name] = version

        for env_var_name, env_var_val in self.env:
            env_vars[env_var_name] = env_var_val

        return actions, env_vars

    def _swap(self, var_man: VariableSetManager, out_name: str,
              out_version: str, version: str) -> (List[Union[ModuleAction, str]], dict):
        """Do the swap as given, but set the additional environment variables."""

        actions, env_vars = super()._swap(var_man, out_name, out_version, version)

        if version:
            vers_var_name = '{}_VERSION'.format(self.name)
            env_vars[vers_var_name] = version

        for env_var_name, env_var_val in self.env:
            env_vars[env_var_name] = env_var_val
