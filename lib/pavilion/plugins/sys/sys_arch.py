import subprocess
import pavilion.system_plugins as system_plugins

class SystemArch( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__( plugin_name='sys_arch', priority=10,
                          is_deferable=False, sub_keys=None )

    def _get( self ):
        """Base method for determining the system architecture."""

        self.values[ None ] = subprocess.check_output(['uname', '-i'])

        try:
            self.values[ None ] = self.values[ None ].strip().decode('UTF-8')
        except:
            raise( system_plugins.SystemPluginError )

        return self.values
