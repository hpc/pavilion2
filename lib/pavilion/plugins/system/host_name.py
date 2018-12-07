import subprocess
import pavilion.system_plugins as system_plugins

class HostName( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'host_name', 10, True )

    def get( self, sys_vars ):
        """Base method for determining the host name."""

        name = subprocess.check_output(['hostname', '-s'])

        name = name.strip().decode('UTF-8')

        sys_vars[ 'host_name' ] = name

        return name
