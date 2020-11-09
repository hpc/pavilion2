import pavilion.system_variables as dumb_system_plugins

class DumbSysVar(dumb_system_plugins.SystemPlugin):

    def __init__(self):
        super().__init__(
            name = 'dumb_sys_var',
            description = "This system is dumb",
            is_deferable = True,
            sub_keys = None)

    def _get( self):
        return "stupid"