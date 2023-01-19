import subprocess
from .base_classes import SystemPlugin


class SystemProcessorCount(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='sys_processor_count',
            description="The system processor count.",
            priority=self.PRIO_CORE)

    def _get( self):
        """Base method for determining the system processor count."""

        name = subprocess.check_output(['grep', '-c', '^processor', '/proc/cpuinfo'])
        return name.strip().decode('UTF-8')
