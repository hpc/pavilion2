import subprocess
import pavilion.system_plugins as system_plugins

class SystemArch( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'lanl_arch' )

    def get( self, sys_vars ):
        """Base method for determining the system architecture."""

        arch = subprocess.check_output(
                                '/usr/projects/hpcsoft/utilities/bin/sys_arch')

        arch = arch.strip().decode('UTF-8')

        sys_vars[ 'lanl_arch' ] = arch

        return arch
