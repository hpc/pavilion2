# These are bits of code that should be somewhere else. This module shouldn't be used.

raise RuntimeError("Never use this module.")

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
