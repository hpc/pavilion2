
class ModuleAction:

    def __init__(self, module_name, version, options=None):
        """Initialize the action.
        :param str module_name: The name of the module
        :param Union(str, None) version: The version of the module. None denotes both unversioned
        modules and loading the default (as interpreted by the module system)
        :param Union(list, None) options: A list of options to pass to the module command.
        """

        self.name = module_name
        self.version = version

        if options is None:
            options = []

        self.options = ' '.join(options)

    def action(self):
        raise NotImplementedError

    def verify(self):
        raise NotImplementedError

    @property
    def module(self):
        if self.version is not None:
            return '{s.name}/{s.version}'.format(s=self)
        else:
            return self.name


class ModuleLoad(ModuleAction):

    def action(self):
        return 'module {s.options} load {s.module}'.format(s=self)

    def verify(self):
        return '# Line that runs a verification.'


class ModuleRemove(ModuleAction):

    def action(self):
        return 'module {s.options} remove {s.module}'.format(s=self)

    def verify(self):
        return '# Verify that it is gone.'

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
        return 'module {s.options} swap {s.old_module} {s.module}'

    def verify(self):
        return '# Verify!!!'