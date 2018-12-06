import subprocess
import pavilion.system_plugins as system_plugins

class SystemArch( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'sys_arch', 10 )

    def get( self, sys_vars ):
        """Base method for determining the system architecture."""

        arch = subprocess.check_output(['uname', '-i'])

        arch = arch.strip().decode('UTF-8')

        sys_vars[ 'sys_arch' ] = arch

        return arch

#    def get( self, sys_vars ):
#        """Base method for determining the system architecture."""
#
#        arch = '$(uname -i)'
#
#        sys_vars[ 'sys_arch' ] = arch
#
#        return arch
