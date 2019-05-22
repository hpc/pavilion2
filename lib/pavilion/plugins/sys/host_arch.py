import subprocess
import pavilion.system_variables as system_plugins

class HostArch(system_plugins.SystemPlugin):

    def __init__(self):
        super().__init__(
            plugin_name='host_arch',
            help_text="The current host's architecture.",
            priority=self.PRIO_DEFAULT,
            is_deferable=True,
            sub_keys=None)

    def _get(self):
        """Base method for determining the host architecture."""

        out = subprocess.check_output(['uname', '-i'])

        return out.strip().decode('utf8')

