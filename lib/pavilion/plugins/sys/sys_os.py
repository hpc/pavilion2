import pavilion.system_plugins as system_plugins

class SystemOS( system_plugins.SystemPlugin ):

    def __init__( self ):
        super().__init__( plugin_name='sys_os', priority=10,
                          is_deferable=False, sub_keys=[ 'ID', 'Version' ] )

    def _get( self ):
        """Base method for determining the operating system and version."""

        rlines = []
        with open('/etc/os-release', 'r') as release:
            rlines = release.readlines()

        for line in rlines:
            if line[:3] == 'ID=':
                self.values[ 'ID' ] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                self.values[ 'Version' ] = line[11:].strip().strip('"')

        return self.values
