"""Built-in commands, as well as the base classes for those commands, go in this
module. While commands are all technically plugins, these are manually added because
its faster than searching for them and loading them as plugins."""

from .base_classes import Command, add_command, get_command, sub_cmd

from ._run import _RunCommand
from ._series import AutoSeries
from .build import BuildCommand
from .cancel import CancelCommand
from .cat import CatCommand
from .clean import CleanCommand
from .config import ConfigCommand
from .graph import GraphCommand
from .list_cmd import ListCommand
from .log import LogCommand
from .ls import LSCommand
from .maint import MaintCommand
from .result import ResultsCommand
from .run import RunCommand
from .series import RunSeries
from .set_status import SetStatusCommand
from .show import ShowCommand
from .status import StatusCommand
from .view import ViewCommand
from .wait import WaitCommand

# Add any new builtin commands to this list.
_builtin_commands = [
    _RunCommand,
    AutoSeries,
    BuildCommand,
    CancelCommand,
    CatCommand,
    CleanCommand,
    ConfigCommand,
    GraphCommand,
    ListCommand,
    LogCommand,
    LSCommand,
    MaintCommand,
    ResultsCommand,
    RunCommand,
    RunSeries,
    SetStatusCommand,
    ShowCommand,
    StatusCommand,
    ViewCommand,
    WaitCommand
]


def register_core_plugins():
    """Add all the builtin plugins and activate them."""

    for cls in _builtin_commands:
        obj = cls()
        obj.activate()


Command.register_core_plugins = register_core_plugins
