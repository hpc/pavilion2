import subprocess
import pavilion.system_plugins as system_plugins

class SystemName( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'lanl_name' )

    def get( self, sys_vars ):
        """Base method for determining the system name."""

        name = subprocess.check_output(
                                '/usr/projects/hpcsoft/utilities/bin/sys_name')

        name = name.strip().decode('UTF-8')

        sys_vars[ 'lanl_name' ] = name

        return name
