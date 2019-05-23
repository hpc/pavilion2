import subprocess
import pavilion.system_variables as system_plugins


class SystemName( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__(
            plugin_name='sys_name', 
            help_text='The system name (not necessarily hostname).',
            priority=self.PRIO_DEFAULT,
            is_deferable=False, 
            sub_keys=None )

    def _get( self ):
        """Base method for determining the system name."""

        name = subprocess.check_output(['hostname', '-s'])
        return name.strip().decode('UTF-8')
