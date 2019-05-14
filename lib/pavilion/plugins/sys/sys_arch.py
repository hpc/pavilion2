import subprocess
import pavilion.system_variables as system_plugins

class SystemArch( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__(
            plugin_name='sys_arch', 
            help_text="The system architecture.",
            priority=10,              
            is_deferable=False, 
            sub_keys=None )

    def _get( self ):
        """Base method for determining the system architecture."""

        arch = subprocess.check_output(['uname', '-i'])
        return arch.strip().decode('utf8')
