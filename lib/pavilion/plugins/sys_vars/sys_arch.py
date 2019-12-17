import subprocess
import pavilion.system_variables as system_plugins


class SystemArch( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__(
            plugin_name='sys_arch', 
            description="The system architecture.",
            priority=self.PRIO_CORE,
            is_deferable=False, 
            sub_keys=None )

    def _get( self ):
        """Base method for determining the system architecture."""

        arch = subprocess.check_output(['uname', '-i'])
        return arch.strip().decode('utf8')
