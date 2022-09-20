import re
import subprocess

from .base_classes import SystemPlugin


class SystemName(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='sys_name',
            description='The system name (not necessarily hostname). By default, the '
                        'hostname minus any trailing number.',
            priority=self.PRIO_CORE)

    def _get(self):
        """Base method for determining the system name."""

        name = subprocess.check_output(['hostname', '-s'])
        name = name.strip().decode('UTF-8')

        # Strip of any trailing numbers from the hostname.
        end = -1
        while name[end:].isdigit():
            end -= 1

        return name[:end+1]
