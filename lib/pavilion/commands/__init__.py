"""Built-in commands, as well as the base classes for those commands, go in this
module. While commands are all technically plugins, these are manually added because
its faster than searching for them and loading them as plugins."""

import importlib
from typing import Union

from pavilion import arguments
from pavilion import errors
from .base_classes import Command, add_command, sub_cmd
from .base_classes import cmd_tracker as _cmd_tracker

# Add any new builtin commands here. The key is the module
# name (which should match command name) and the value is the
# command class within that module.
_builtin_commands = {
    '_run': '_RunCommand',
    '_series': 'AutoSeries',
    'build': 'BuildCommand',
    'cancel': 'CancelCommand',
    'cat': 'CatCommand',
    'clean': 'CleanCommand',
    'config': 'ConfigCommand',
    'graph': 'GraphCommand',
    'group': 'GroupCommand',
    'list_cmd': 'ListCommand',
    'log': 'LogCommand',
    'ls': 'LSCommand',
    'maint': 'MaintCommand',
    'result': 'ResultsCommand',
    'run': 'RunCommand',
    'series': 'RunSeries',
    'set_status': 'SetStatusCommand',
    'show': 'ShowCommand',
    'status': 'StatusCommand',
    'view': 'ViewCommand',
    'wait': 'WaitCommand',
}

# Add aliases for each builtin command here.
_aliases = {
    'set_status': ['status_set'],
    'result': ['results'],
    'list_cmd': ['list'],
}


def register_core_plugins():
    """Add all the builtin plugins and activate them."""

    # Add fake options for each command and their aliases.
    subp = arguments.get_subparser()

    # When we 'get' the command below, we'll replace this subparser
    # with the real one.
    for cmd in _builtin_commands.keys():
        dummy_parser = subp.add_parser(cmd, aliases=_aliases.get(cmd, []),
                                       add_help=False)
        dummy_parser.add_argument('--help', '-h', action='store_true')


# Pavilion looks for this function on the Plugin class
Command.register_core_plugins = register_core_plugins


def get_command(command_name: str) -> Union[None, Command]:
    """Return the command of the given name. This assumes the command
    has already been validated as being one that exists.
    """

    _commands = _cmd_tracker()

    # If we already activated the command, just return it.
    if command_name in _commands:
        return _commands[command_name]

    # Find the real command from amongst the aliases.
    if command_name not in _builtin_commands:
        for alias_cmd, aliases in _aliases.items():
            if command_name in aliases:
                command_name = alias_cmd

    if command_name not in _builtin_commands:
        raise errors.CommandError(
            "Could not find command '{}'. You should always get an error from "
            "the argument parser, and never this one.".format(command_name))

    command_class = _builtin_commands[command_name]
    mod = importlib.import_module('.' + command_name, 'pavilion.commands')
    if not hasattr(mod, command_class):
        raise errors.CommandError(
            "Could not find class '{}' for builtin command '{}'. If you're seeing this, "
            "then a class was improperly registered in pavilion.commands."
            .format(command_class, command_name))

    if command_name not in _commands:
        command: Command = getattr(mod, command_class)()
        # If we've never seen this command, activate it.  Activation will also replace the dummy
        # subcommand in the argument parser.
        command.activate()

    return _commands[command_name]


def load(*cmds: str):
    """Load the given commands. If no commands are given, load all commands."""

    if not cmds:
        cmds = _builtin_commands.keys()

    for cmd in cmds:
        get_command(cmd)
