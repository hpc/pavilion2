from yapsy import IPlugin
import logging
import re
import subprocess as sp

LOGGER = logging.getLogger('pav.{}'.format(__name__))


class ModuleSystemError(RuntimeError):
    pass


_WRAPPED_MODULES = {}


def add_wrapped_module(module_wrapper):
    """Add the module wrapper to the set of wrapped modules.
    :param ModuleWrapper module_wrapper: The module_wrapper class for the module.
    :return: None
    :raises KeyError: On module version conflict.
    """

    name = module_wrapper.name
    version = module_wrapper.version
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


def remove_wrapped_module(module_wrapper):
    """Remove the indicated module_wrapper from the set of wrapped module.
    :param ModuleWrapper module_wrapper: The module_wrapper to remove, if it exists.
    :returns None:
    """

    name = module_wrapper.name
    version = module_wrapper.version

    if name in _WRAPPED_MODULES and version in _WRAPPED_MODULES[name]:
        del _WRAPPED_MODULES[name][version]

        if not _WRAPPED_MODULES[name]:
            del _WRAPPED_MODULES[name]


class ModuleInfo:
    def __init__(self, name):

        self.name = name
        self.versions = []
        self.default = None


class ModuleWrapper(IPlugin):

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
        self.version = version
        self.priority = priority
        self.path = path

        if self._MODULE_SYSTEM is None or self._MODULE_CMD is None:
            raise RuntimeError("You must use the 'find_module_system' class method before"
                               "instantiating a ModuleWrapper (or subclasses).")

    @property
    def module(self):
        if self.version is not None:
            return '{}/{}'.format(self.name, self.version)
        else:
            return self.name

    def activate(self):
        """Add this module to the wrapped module list."""

        add_wrapped_module(self)

    def deactivate(self):
        """Remove this module from the wrapped module list."""

        remove_wrapped_module(self)

    @classmethod
    def find_module_system(cls, pav_config):
        """Figure out which module system we're using, and set the module command in the class.""
        :param pav_config: The pavilion configuration.
        :return: None
        :raises ModuleSystemError: When we can't find the module system.
        """

        if cls._MODULE_CMD is not None or cls._MODULE_SYSTEM is not None:
            LOGGER.warning("In ModuleWrapper, find_module_system should only be called once.")
            return

        cls._MODULE_CMD = pav_config.get('module_command')

        version_cmd = [cls._MODULE_CMD, '-v']
        try:
            proc = sp.Popen(version_cmd, stderr=sp.STDOUT, stdout=sp.PIPE)
        except FileNotFoundError as err:
            raise ModuleSystemError("Could not find module cmd '{}' ({})."
                                    .format(cls._MODULE_CMD, err))

        result = proc.wait()
        stdout, _ = proc.communicate()

        if result != 0:
            err_msg = "Error getting module version with cmd '{}'".format(version_cmd)
            LOGGER.error(err_msg)
            LOGGER.error(stdout)
            raise ModuleSystemError(err_msg)

        for line in stdout.split('\n'):
            if "Modules Release" in line:
                cls._MODULE_SYSTEM = cls.EMOD
                break
            elif "Modules based on Lua" in line:
                cls._MODULE_SYSTEM = cls.LMOD

        if cls._MODULE_SYSTEM is None:
            raise ModuleSystemError("Could not identify a module system.")

    def load(self, system_info):
        """Generates the commands and environment variables needed to load the module.
        :param system_info: The sys variable dictionary, which should contain relevant information
        about the system.
        returns: ([commands], {env})
        """

        raise NotImplementedError

    def remove(self, system_info):
        """Generates the commands and environment variables needed to remove the module.
        :param system_info: The sys variable dictionary, which should contain relevant information
        about the system.
        returns: ([commands], {env})
        """

        raise NotImplementedError

    def swap(self, old_module, system_info):
        """Generates the commands and environment variables needed to swap the given module for
        this one.
        :param str old_module: The module to replace with this one.
        :param dict system_info: The sys variable dictionary, which should contain relevant
        information
        about the system.
        returns: ([commands], {env})
        """

        raise NotImplementedError


class DefaultModuleLoader(ModuleWrapper):

    def __init__(self, name, version):
        """A basic wrapper for wrapping otherwise unwrapped modules.
        :param name: The name of the module to load.
        :param version: The version of the module to load.
        """
        super(DefaultModuleLoader).__init__(name, '<unwrapped>', version=version)

    def load(self, system_info):
        """In the basic case, simply load the module by name and version."""

        return ['{s._MODULE_CMD} load {s.module}'.format(s=self)], {}

    def swap(self, old_module, system_info):
        """Perform a simple module swap."""

        swap_cmd = '{s._MODULE_CMD} swap {old_module} {s.module}'\
                   .format(s=self, old_module=old_module)

        return [swap_cmd], {}

    def remove(self, system_info):
        """Remove this module from the environment."""

    # These should do nothing, as this isn't part of the module plugin system.
    def activate(self):
        pass

    def deactivate(self):
        pass


class ModuleSwapper(ModuleWrapper):
    """A module wrapper for swapping two modules."""

    def __init__(self, old_name, old_version, name, version):
        """Set the name of the old module to remove, and the new to add.
        :param str old_name: The name of the module to swap out.
        :param Union(str, None) old_version: The version of the module to swap out.
        :param str name: The name of the module to swap in.
        :param Union(str, None) version: The version of the module to swap in.
        """

        if self.NAME_VERS_RE.match(old_name) is None:
            raise ModuleSystemError("Invalid module name for swapping out: '{}'".format(old_name))
        if old_version is not None and self.NAME_VERS_RE.match(old_version) is None:
            raise ModuleSystemError("Invalid module version for swapping out: '{}'"
                                    .format(old_name))

        self._old_name = old_name
        self._old_version = old_version

        super(ModuleSwapper).__init__(name, path='<unwrapped swap>', version=version)

    @property
    def old_module(self):
        if self._old_version is not None:
            return '{}/{}'.format(self._old_name, self._old_version)
        else:
            return self._old_name

    def get_module_loads(self, system_info):
        """Swap the old module for the new."""

        return ['{s._MODULE_CMD} swap {s.old_module} {s.module}'.format(s=self)]


class ModuleRemover(ModuleWrapper):
    """A module wrapper for removing modules from the environment."""
    def __init__(self, name, version):
        super(ModuleRemover).__init__(name, '<unwrapped_remover>', version=version)

    def get_module_loads(self, system_info):
        return ['{s._MODULE_CMD} remove {s.module}'.format(s=self)]