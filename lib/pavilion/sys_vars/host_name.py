import subprocess
from .base_classes import SystemPlugin


class HostName(SystemPlugin):

    def __init__( self ):
        super().__init__(
            name='host_name',
            description="The target host's hostname.",
            priority=self.PRIO_CORE,
            is_deferable=True)

    def _get( self ):
        """Base method for determining the host name."""

        out = subprocess.check_output(['hostname', '-s'])
        return out.strip().decode('UTF-8')
