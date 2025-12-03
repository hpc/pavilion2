import os
from .base_classes import SystemPlugin


class HostCPUs(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='host_cpus',
            description="The system processor count.",
            priority=self.PRIO_CORE)

    def _get(self):
        """Base method for determining the system processor count."""

        return str(os.cpu_count())
