import subprocess
import pavilion.system_plugins as system_plugins

class SystemArch( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'sys_arch', 11, True )

    def get( self, sys_vars ):
        """LANL method for determining the system architecture."""

        arch = subprocess.check_output(
                                '/usr/projects/hpcsoft/utilities/bin/sys_arch')

        arch = arch.strip().decode('UTF-8')

        sys_vars[ 'sys_arch' ] = arch

        return arch
