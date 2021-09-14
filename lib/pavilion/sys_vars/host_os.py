import pavilion.system_variables as system_plugins
from pathlib import Path


class HostOS(system_plugins.SystemPlugin):

    def __init__(self):
        super().__init__(
            name='host_os',
            description="The target host's OS info (name, version).",
            priority=self.PRIO_CORE,
            is_deferable=True)

    def _get(self):
        """Base method for determining the operating host and version."""

        with Path('/etc/os-release').open('r') as release:
            rlines = release.readlines()

        os = {}

        for line in rlines:
            if line[:3] == 'ID=':
                os['name'] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                os['version'] = line[11:].strip().strip('"')

        return os
