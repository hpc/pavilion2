import subprocess
import pavilion.varaibles
import pavilion.system_plugins as system_plugins

class HostName( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( plugin_name='host_name', priority=10, 
                        is_deferable=True, sub_keys=None )

    def _get( self ):
        """Base method for determining the host name."""

        self.values[ None ] = subprocess.check_output(['hostname', '-s'])
        self.values[ None ] = self.values[ None ].strip().decode('UTF-8')

        return self.values
