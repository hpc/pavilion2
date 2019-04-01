import subprocess
import pavilion.system_variables as system_plugins

class HostArch( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__( plugin_name='host_arch', priority=10,
                          is_deferable=True, sub_keys=None )

    def _get( self ):
        """Base method for determining the host architecture."""

        self.values[ None ] = subprocess.check_output(['uname', '-i'])

        try:
            self.values[ None ] = self.values[ None ].strip().decode('UTF-8')
        except:
            raise( system_plugins.SystemPluginError )

        return self.values
