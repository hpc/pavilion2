import subprocess
import pavilion.system_variables as system_plugins

class SystemName( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__( plugin_name='sys_name', priority=10,
                          is_deferable=False, sub_keys=None )

    def _get( self ):
        """Base method for determining the system name."""

        self.values[ None ] = subprocess.check_output(['hostname', '-s'])
        self.values[ None ] = self.values[ None ].strip().decode('UTF-8')

        return self.values
