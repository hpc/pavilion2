from pathlib import Path
from .base_classes import SystemPlugin


class Platform(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='platform',
            description="The system platform (name, version).",
            priority=self.PRIO_CORE)

    def _get(self):
        """Base method for determining the system platform."""

        with Path('/etc/os-release').open() as release:
            rlines = release.readlines()

        name = ""
        version = ""

        for line in rlines:
            if line[:3] == 'ID=':
                name = line[3:].strip().strip('"')
            elif line[:11] == 'VERSION_ID=':
                version = line[11:].strip().strip('"')

        return f"{name}-{version}"
