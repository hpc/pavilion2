from pathlib import Path
from .base_classes import SystemPlugin


class HostOS(SystemPlugin):

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

        os_info = {}

        for line in rlines:
            if line[:3] == 'ID=':
                os_info['name'] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                os_info['version'] = line[11:].strip().strip('"')

        return os_info
