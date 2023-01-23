import subprocess
from .base_classes import SystemPlugin


class HostCPUs(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='host_cpus',
            description="The system processor count.",
            priority=self.PRIO_CORE)

    def _get( self):
        """Base method for determining the system processor count."""

        name = subprocess.check_output(['grep', '-c', '^processor\s*:\s*\d*', '/proc/cpuinfo'])
        return name.strip().decode('UTF-8')
