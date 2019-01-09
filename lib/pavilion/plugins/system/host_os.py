import pavilion.system_plugins as system_plugins

class HostOS( system_plugins.SystemPlugins ):

    def __init__( self ):
        super.__init__( 'host_os', 10, True, [ 'ID', 'Version' ] )

    def get( self, sub_key=None ):
        """Base method for determining the operating host and version."""

        if sub_key not in self.sub_keys:
            raise KeyError("Sub-key '{}' not found on sys variable {}.".format(
                           sub_key, self.name))

        with open('/etc/os-release', 'r') as release:
            rlines = release.readlines()

        for line in rlines:
            if line[:3] == 'ID=':
                self.values[ 'ID' ] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                self.values[ 'Version' ] = line[11:].strip().strip('"')

        return self.values[ sub_key ]
