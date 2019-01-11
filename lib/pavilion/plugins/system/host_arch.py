import subprocess
import pavilion.variables
import pavilion.system_plugins as system_plugins

class HostArch( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'host_arch', 10, True, [ None ] )

    def _get( self ):
        """Base method for determining the host architecture."""

        if sub_key not in self.sub_keys:
            raise KeyError("Sub-key '{}' not found on sys variable {}.".format(
                           sub_key, self.name))

        self.values[ None ] = subprocess.check_output(['uname', '-i'])
        self.values[ None ] = self.values[ None ].strip().decode('UTF-8')

        return self.values
