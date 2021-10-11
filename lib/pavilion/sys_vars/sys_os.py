from pathlib import Path
from .base_classes import SystemPlugin


class SystemOS(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='sys_os',
            description="The system os info (name, version).",
            priority=self.PRIO_CORE)

    def _get(self):
        """Base method for determining the operating system and version."""

        with Path('/etc/os-release').open() as release:
            rlines = release.readlines()

        os_info = {}

        for line in rlines:
            if line[:3] == 'ID=':
                os_info['name'] = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                os_info['version'] = line[11:].strip().strip('"')

        return os_info
