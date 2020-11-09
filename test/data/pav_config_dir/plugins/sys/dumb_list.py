import pavilion.system_variables as dumb_system_plugins


class DumbListVar(dumb_system_plugins.SystemPlugin):

    def __init__(self):
        super().__init__(
            name='dumb_list',
            description="This list variable is dumb",
            is_deferable=True)

    def _get(self):
        return ["d", "u", "m", "b"]