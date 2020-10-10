import inspect
import logging
import re

from pavilion.module_actions import ModuleLoad, ModuleSwap, ModuleUnload
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


def get_module_wrapper(name, version=None):
    """Finds and returns a module wrapper to match the specified module
name and version. The default module wrapper is returned if a match isn't
found.

:param str name: The name of the module.
:param Union(str, None) version: The version requested. If None is specified,
                                 this will look for the version-generic
                                 module wrapper for this module.
:rtype: ModuleWrapper
"""

    if name in _WRAPPED_MODULES:
        if version in _WRAPPED_MODULES[name]:
            # Grab the version specific wrapper.
            return _WRAPPED_MODULES[name][version]
        elif None in _WRAPPED_MODULES[name]:
            # Grab the generic wrapper for this module
            return _WRAPPED_MODULES[name][None]

    return ModuleWrapper(name, '<default>', version=version)


def list_module_wrappers():
    """Returns a list of all loaded module wrapper plugins.

:rtype: list
"""
    return list(_WRAPPED_MODULES.keys())


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

    def load(self, var_man, requested_version=None):
        """Generate the list of module actions and environment changes to load
this module.

:param dict var_man: The system info dictionary of variables, from the
                 system plugins.
:param str requested_version: The version requested to load.
:return: A list of actions (or bash command strings), and a dict of
         environment changes.
:rtype: (Union(str, ModuleAction), dict)
:raises ModuleWrapperError: If the requested version does not work with
                            this instance.
"""

        del var_man  # Arguments meant for use when overriding this.

        version = self.get_version(requested_version)

        return [ModuleLoad(self.name, version)], {}

    def swap(self, var_man, out_name, out_version, requested_version=None):
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

        del var_man  # Arguments meant for use when overriding this.

        version = self.get_version(requested_version)

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

        del var_man  # Arguments meant for use when overriding this.

        version = self.get_version(requested_version)

        return [ModuleUnload(self.name, version)], {}
