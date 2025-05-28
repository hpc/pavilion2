from yapsy import IPlugin

from pavilion.errors import LoggingPluginError


class LoggingPlugin(IPlugin.IPlugin):

    PRIO_CORE = 0
    PRIO_COMMON = 10
    PRIO_USER = 20

    NAME_VERS_RE = re.compile(r'^[a-zA-Z0-9_.-]+$')

    def __init__(self, plugin_name: str, help_text: str, priority=self.PRIO_COMMON):
        super().__init__()

        if self.NAME_VERS_RE.match(name) is None:
            raise LoggingPluginError(
                "Invalid module name: '{}'"
                .format(name))

    def log():
        ...
