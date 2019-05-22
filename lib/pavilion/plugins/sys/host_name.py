import subprocess
import pavilion.system_variables as system_plugins


class HostName( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__(
            plugin_name='host_name',
            help_text="The target host's hostname.",
            priority=self.PRIO_DEFAULT,
            is_deferable=True,
            sub_keys=None)

    def _get( self ):
        """Base method for determining the host name."""

        out = subprocess.check_output(['hostname', '-s'])
        return out.strip().decode('UTF-8')

