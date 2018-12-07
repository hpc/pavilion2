import subprocess
import pavilion.system_plugins as system_plugins

class HostArch( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'host_arch', 10, True )

    def get( self, sys_vars ):
        """Base method for determining the host architecture."""

        arch = subprocess.check_output(['uname', '-i'])

        arch = arch.strip().decode('UTF-8')

        sys_vars[ 'host_arch' ] = arch

        return arch
