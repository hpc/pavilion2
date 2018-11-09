from pavilion.module_actions import ModuleLoad, ModuleSwap, ModuleRemove
from yapsy import IPlugin
import logging
import re

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class ModuleSystemError(RuntimeError):
    pass


_WRAPPED_MODULES = {}


def add_wrapped_module(module_wrapper, version):
    """Add the module wrapper to the set of wrapped modules.
    :param ModuleWrapper module_wrapper: The module_wrapper class for the module.
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
        raise ModuleSystemError("Two modules for the same module/version, with the same "
                                "priority {}, {}."
                                .format(module_wrapper, _WRAPPED_MODULES[name][version]))


def remove_wrapped_module(module_wrapper, version):
    """Remove the indicated module_wrapper from the set of wrapped module.
    :param ModuleWrapper module_wrapper: The module_wrapper to remove, if it exists.
    :param Union(str, None) version: The specific version to remove.
    :returns None:
    """

    name = module_wrapper.name

    if name in _WRAPPED_MODULES and version in _WRAPPED_MODULES[name]:
        del _WRAPPED_MODULES[name][version]

        if not _WRAPPED_MODULES[name]:
            del _WRAPPED_MODULES[name]


def get_module_wrapper(name, version):

    if name in _WRAPPED_MODULES:
        if version in _WRAPPED_MODULES[name]:
            # Grab the version specific wrapper.
            return _WRAPPED_MODULES[name][version]
        elif None in _WRAPPED_MODULES[name]:
            # Grab the generic wrapper for this module
            return _WRAPPED_MODULES[name][None]

    return ModuleWrapper(name, version)


class ModuleWrapper(IPlugin.IPlugin):

    _MODULE_SYSTEM = None
    _MODULE_CMD = None
    LMOD = 'lmod'
    EMOD = 'emod'
    NONE = 'none'

    PRIO_DEFAULT = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self, name, path, version=None, priority=PRIO_DEFAULT):
        """Initialize the module wrapper instance. This must be overridden in plugins
        as the plugin system can't handle the arguments
        :param str name: The name of the module being wrapped.
        :param str path: Where this wrapper is defined. This makes it easy for users to resolve
        problems with plugins, by letting them know where the plugin actually came from.
        :param str version: The version of module file to wrap. None denotes a wild version or a
        version-less modulefile.
        :param int priority: The priority of this wrapper. It will replace identical wrappers of a
        lower priority when loaded. Use
        """

        if self.NAME_VERS_RE.match(name) is None:
            raise ModuleSystemError("Invalid module name: '{}'".format(name))
        if version is not None and self.NAME_VERS_RE.match(version) is None:
            raise ModuleSystemError("Invalid module name: '{}'".format(name))

        self.name = name
        self.__version = version
        self.priority = priority
        self.path = path

        if self._MODULE_SYSTEM is None or self._MODULE_CMD is None:
            raise RuntimeError("You must use the 'find_module_system' class method before"
                               "instantiating a ModuleWrapper (or subclasses).")

    def get_version(self, requested_version):
        """Get the version of the module to load, given the requested version and the version
        set in the instance. This should always be used to figure out what version to load.
        :param Union(str, None) requested_version: The version requested by the user.
        :return: The version that should be loaded.
        """

        if self.__version is not None and requested_version != self.__version:
            raise ModuleWrapperError("Version mismatch. A module wrapper specifically for "
                                     "version '{s.__version}' of '{s.name}' was used with "
                                     "a non-matching requested version '{requested}"
                                     .format(s=self, requested=requested_version))

        return requested_version

    def activate(self):
        """Add this module to the wrapped module list."""

        add_wrapped_module(self, self.__version)

    def deactivate(self):
        """Remove this module from the wrapped module list."""

        remove_wrapped_module(self, self.__version)

    def load(self, sys_info, requested_version=None):
        """Generate the list of module actions and environment changes to load this module.
        :param sys_info: The system info dictionary of variables, from the system plugins.
        :param requested_version: The version requested to load.
        :return: A list of actions (or bash command strings), and a dict of environment changes.
        :rtype: (Union(str, ModuleAction), dict)
        :raises ModuleWrapperError: If the requested version does not work with this instance.
        """

        version = self.get_version(requested_version)

        return [ModuleLoad(self.name, version)], {}

    def swap(self, sys_info, out_name, out_version, requested_version=None):
        """Swap out the 'out' module and swap in the new module.
        :param sys_info: The system info dictionary of variables, from the system plugins.
        :param out_name: The name of the module to swap out.
        :param out_version: The version of the module to swap out.
        :param requested_version: The version requested to load.
        :return: A list of actions (or bash command strings), and a dict of environment changes.
        :rtype: (Union(str, ModuleAction), dict)
        :raises ModuleWrapperError: If the requested version does not work with this instance.
        """

        version = self.get_version(requested_version)

        return [ModuleSwap(self.name, version, out_name, out_version)]

    def remove(self, sys_info, requested_version=None):
        """Remove this module from the environment.
        :param sys_info: The system info dictionary of variables, from the system plugins.
        :param requested_version: The version requested to load.
        :return: A list of actions (or bash command strings), and a dict of environment changes.
        :rtype: (Union(str, ModuleAction), dict)
        :raises ModuleWrapperError: If the requested version does not work with this instance.
        """

        version = self.get_version(requested_version)

        return [ModuleRemove(self.name, version)], {}



