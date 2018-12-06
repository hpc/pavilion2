import subprocess
import pavilion.system_plugins as system_plugins

class SystemOS( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'sys_os' )
        self.id = None
        self.version = None

    def get( self, sys_vars ):
        """LANL method for determining the system OS."""

        os = subprocess.check_output(
                                  '/usr/projects/hpcsoft/utilities/bin/sys_os')

        os = os.strip().decode('UTF-8')

        if os[0:4] == 'toss':
            self.id = os[:4]
            self.version = os[4:]
        elif os[0:3] == 'cle':
            self.id = os[:3]
            self.version = os[3:]

        sys_vars[ 'sys_os' ] = {'ID': self.id, 'Version': self.version}

        return {'ID': self.id, 'Version': self.version}

#    def get( self, sys_vars ):
#        """LANL method for determining the system OS."""
#
#        os = '$(/usr/projects/hpcsoft/utilities/bin/sys_os)'
#
#        sys_vars[ 'sys_os' ] = { 'ID': os, 'Version': None }
#
#        return { 'ID': os, 'Version': None }
