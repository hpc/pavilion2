import pavilion.system_variables as dumb_system_plugins

class DumbOSVar(dumb_system_plugins.SystemPlugin):


    def __init__(self):
        super().__init__(
            name = 'dumb_os',
            description = "This OS variable is dumb",
            is_deferable = False,
            sub_keys = None)

    def _get(self):
        return "bieber"