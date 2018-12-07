import pavilion.system_plugins as system_plugins

class HostOS( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'host_os', 10, True )
        self.id = None
        self.version = None

    def get( self, sys_vars ):
        """Base method for determining the operating host and version."""

        with open('/etc/os-release', 'r') as release:
            rlines = release.readlines()

        for line in rlines:
            if line[:3] == 'ID=':
                self.id = line[3:].strip()
            elif line[:11] == 'VERSION_ID=':
                self.version = line[11:].strip()

        if self.id != None and self.id[0] == '"' and self.id[-1] == '"':
            self.id = self.id[1:-1]

        if self.version != None and self.version[0] == '"' \
                                and self.version[-1] == '"':
            self.version = self.version[1:-1]

        sys_vars[ 'host_os' ] = {'ID': self.id, 'Version': self.version}

        return {'ID': self.id, 'Version': self.version}
