import subprocess
from .base_classes import SystemPlugin
import re


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

        name_re = re.compile(r'([a-zA-Z]+[a-zA-Z0-9_-]*[a-zA-Z_-]+)([0-9]*)$')

        match = name_re.match(name)
        name = match.groups()[0]

        return name

