
class ModuleAction:

    def __init__(self, module_name, version=None):
        """Initialize the action.
        :param str module_name: The name of the module
        :param Union(str, None) version: The version of the module. None
        denotes both unversioned modules and loading the default (as
        interpreted by the module system)
        """

        self.name = module_name
        self.version = version if version is not None else ''

    def action(self):
        raise NotImplementedError

    def verify(self):
        raise NotImplementedError

    @property
    def module(self):
        if self.version:
            return '{s.name}/{s.version}'.format(s=self)
        else:
            return self.name


class ModuleLoad(ModuleAction):

    def action(self):
        return ['module load {s.module}'.format(s=self)]

    def verify(self):
        return ['verify_module_loaded $TEST_ID {s.name} '.format(s=self)
                    '{s.version}'.format(s=self)]


class ModuleRemove(ModuleAction):

    def action(self):
        return ['module remove {s.module}'.format(s=self)]

    def verify(self):
        return ['verify_module_removed $TEST_ID {s.name} '.format(s=self)
                    '{s.version}'.format(s=self)]


class ModuleSwap(ModuleAction):

    def __init__(self, module_name, version, old_module_name, old_version):
        super(ModuleSwap).__init__(module_name, version)

        self.old_name = old_module_name
        self.old_version = old_version

    @property
    def old_module(self):
        if self.old_version is not None:
            return '{s.old_name}/{s.old_version}'.format(s=self)
        else:
            return self.old_name

    def action(self):
        actions = ['if $(module list 2>&1 | grep {s.old_name})'.format(s=self)
                   'then',
                   '    module swap $(module list 2>&1 | grep '
                       '{s.old_name}) {s.module}'.format(s=self),
                   'else',
                   '    module load {s.module}'.format(s=self)
                   'fi']
        return actions

    def verify(self):
        return ['verify_module_loaded $TEST_ID {s.name} '.format(s=self)
                    '{s.version}'.format(s=self),
                'verify_module_removed $TEST_ID {s.old_name} '.format(s=self)
                    '{s.old_version}'.format(s=self)]
