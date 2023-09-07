import re
import subprocess

from pavilion.sys_vars import SystemPlugin


class SystemName(SystemPlugin):

    def __init__(self):
        super().__init__(
            name='sys_name',
            description='System Name override for the demo_host. Always returns the name '
                        '"demo_host".')

    def _get(self):
        """Base method for determining the system name."""

        # Our sys_name plugin for the demo always returns the 
        # host name 'demo_host'.  
        return "demo_host"
