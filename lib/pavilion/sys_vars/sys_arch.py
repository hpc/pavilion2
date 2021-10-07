import subprocess
from .base_classes import SystemPlugin


class SystemArch(SystemPlugin):

    def __init__( self ):
        super().__init__(
            name='sys_arch',
            description="The system architecture.",
            priority=self.PRIO_CORE)

    def _get( self ):
        """Base method for determining the system architecture."""

        arch = subprocess.check_output(['uname', '-i'])
        return arch.strip().decode('utf8')
