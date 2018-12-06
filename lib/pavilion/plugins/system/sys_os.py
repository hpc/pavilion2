import pavilion.system_plugins as system_plugins

class SystemOS( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'sys_os', 10 )
        self.id = None
        self.version = None

    def get( self, sys_vars ):
        """Base method for determining the operating system and version."""

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

        sys_vars[ 'sys_os' ] = {'ID': self.id, 'Version': self.version}

        return {'ID': self.id, 'Version': self.version}

#    def get( self, sys_vars ):
#        """Base method for determining the operating system and version."""
#
#        self.id = "$( '^ID=' /etc/os-release | sed 's/ID=//' | sed 's/\"//g')"
#        self.version = "$( grep '^VERSION_ID=' /etc/os-release | " + \
#                       "sed 's/VERSION_ID=//' | sed 's\"//g')"
#
#        sys_vars[ 'sys_os' ] = {'ID': self.id, 'Version': self.version}
#
#        return {'ID': self.id, 'Version': self.version}
