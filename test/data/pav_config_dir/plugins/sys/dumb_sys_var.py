import pavilion.sys_vars.base_classes as dumb_system_plugins


class DumbSysVar(dumb_system_plugins.SystemPlugin):
    """An always deferred system variable."""

    def __init__(self):
        super().__init__(
            name='dumb_sys_var',
            description="This system is dumb",
            is_deferable=True)

    def _get( self):
        return "stupid"
