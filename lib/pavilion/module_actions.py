"""Defines the how to perform module loads, swaps and unloads."""


class ModuleAction:
    """The base module action class."""

    def __init__(self, module_name, version=None):
        """Each module action is specific to a module name and optional version.

:param str module_name: The name of the module
:param Union(str, None) version: The version of the module. None
    denotes both un-versioned modules and loading the default (as
    interpreted by the module system)
"""

        self.name = module_name
        self.version = version if version is not None else ''

    def action(self):
        """Returns a list of bash commands that should perform the action for
the given module.

:rtype: list(str)
"""
        raise NotImplementedError

    def verify(self):
        """Returns a list of bash commands that should verify that the module
action has been performed successfully. These should set the test
status to ENV_FAILED, and exit the bash script with a non-zero return code."""
        raise NotImplementedError

    @property
    def module(self):
        """A properly formatted module name for the given module and version."""
        if self.version:
            return '{s.name}/{s.version}'.format(s=self)
        else:
            return self.name


class ModuleLoad(ModuleAction):
    """Provides module loading commands and verification."""

    def action(self):
        return ['module load {s.module}'
                .format(s=self)]

    def verify(self):
        return ['verify_module_loaded $TEST_ID {s.name} {s.version}'
                .format(s=self)]


class ModuleUnload(ModuleAction):
    """Provides module unloading commands and verification."""

    def action(self):
        return ['module unload {s.module}'.format(s=self)]

    def verify(self):
        return ['verify_module_removed $TEST_ID {s.name} {s.version}'
                .format(s=self)]


class ModuleRestore(ModuleAction):
    """Provides module restore commands and verification for collections.
       This should only be used with Cray PrgEnv-... collections for now.  The
       check for this working is the presence of a 'cpe-' module matching
       the environment of the collection."""

    def action(self):
        return ['module restore {s.module}'.format(s=self)]

    def verify(self):
        cmd = ['verify_module_loaded',
               '$TEST_ID',
               'cpe-{s}'.format(s=self.name.split('-')[1]),
               '{s.version}'.format(s=self)]
        return [" ".join(cmd)]


class ModuleSwap(ModuleAction):
    """Provides module swapping commands and verification."""

    def __init__(self, module_name, version, old_module_name, old_version):
        super().__init__(module_name, version)

        self.old_name = old_module_name
        self.old_version = old_version

    @property
    def old_module(self):
        if self.old_version:
            return '{s.old_name}/{s.old_version}'.format(s=self)
        else:
            return self.old_name

    def action(self):
        actions = [
            # Find the currently loaded matching module. Note, some people
            # like to rely on the regex in their module_wrapper plugins.
            'old_module=$(module -t list 2>&1 | '
            'grep -E \'^{s.old_name}(/|$)\')',
            # Check the result of the last command.
            'if [[ $? == 0 ]]; then',
            '    module swap $old_module {s.module}',
            'else',
            '    module load {s.module}',
            'fi']
        return [a.format(s=self) for a in actions]

    def verify(self):
        lines = ['verify_module_loaded $TEST_ID {s.name} {s.version}',
                 'verify_module_removed $TEST_ID {s.old_name} {s.old_version}']

        return [l.format(s=self) for l in lines]
