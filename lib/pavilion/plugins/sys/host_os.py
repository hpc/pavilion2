import pavilion.system_variables as system_plugins
from pathlib import Path


class HostOS(system_plugins.SystemPlugin):

    def __init__(self):
        super().__init__(plugin_name='host_os', priority=10,
                         is_deferable=True, sub_keys=['ID', 'Version'])

    def _get(self):
        """Base method for determining the operating host and version."""

        with Path('/etc/os-release').open('r') as release:
            rlines = release.readlines()

        for line in rlines:
            if line[:3] == 'ID=':
                self.values['ID'] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                self.values['Version'] = line[11:].strip().strip('"')

        return self.values
