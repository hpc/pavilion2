import subprocess
import pavilion.system_plugins as system_plugins

class SystemOS( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'lanl_os' )
        self.id = None
        self.version = None

    def get( self, sys_vars ):
        """Base method for determining the system OS."""

        os = subprocess.check_output(
                                  '/usr/projects/hpcsoft/utilities/bin/sys_os')

        os = os.strip().decode('UTF-8')

        if os[0:4] == 'toss':
            self.id = os[:4]
            self.version = os[4:]
        elif os[0:3] == 'cle':
            self.id = os[:3]
            self.version = os[3:]

        sys_vars[ 'lanl_os' ] = {'ID': self.id, 'Version': self.version}

        return {'ID': self.id, 'Version': self.version}
