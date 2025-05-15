"""Built-in commands, as well as the base classes for those commands, go in this
module. While commands are all technically plugins, these are manually added because
its faster than searching for them and loading them as plugins."""

import importlib
from typing import Union

from pavilion import errors
from .base_classes import Command, add_command, sub_cmd, setup_arguments
from .base_classes import cmd_tracker as _cmd_tracker

# Add any new builtin commands here. The key is the command
# name, and the value is a tuple of the module name and plugin
# class within that module.
_builtin_commands = {
    '_run':       ('_run', '_RunCommand'),
    '_series':    ('_series', 'AutoSeries'),
    'build':      ('build', 'BuildCommand'),
    'cancel':     ('cancel', 'CancelCommand'),
    'cat':        ('cat', 'CatCommand'),
    'clean':      ('clean', 'CleanCommand'),
    'config':     ('config', 'ConfigCommand'),
    'graph':      ('graph', 'GraphCommand'),
    'group':      ('group', 'GroupCommand'),
    'list':       ('list_cmd', 'ListCommand'),
    'log':        ('log', 'LogCommand'),
    'ls':         ('ls', 'LSCommand'),
    'maint':      ('maint', 'MaintCommand'),
    'result':     ('result', 'ResultsCommand'),
    'run':        ('run', 'RunCommand'),
    'series':     ('series', 'RunSeries'),
    'set_status': ('set_status', 'SetStatusCommand'),
    'show':       ('show', 'ShowCommand'),
    'status':     ('status', 'StatusCommand'),
    'view':       ('view', 'ViewCommand'),
    'wait':       ('wait', 'WaitCommand'),
}

# Add aliases for each builtin command here.
_builtin_aliases = {
    'set_status': ['status_set'],
    'result': ['results'],
}


def register_core_plugins():
    """For commands we don't actually want to load all the command modules - we'll probably only
    need one.  We'll just put in place dummy commands """

    for cmd_name in _builtin_commands.keys():
        # Make a dummy command for each of our builtin commands.
        cmd = Command(cmd_name, '', aliases = _builtin_aliases.get(cmd_name, []), is_dummy=True)
        add_command(cmd)

# Pavilion looks for this function on the Plugin class
Command.register_core_plugins = register_core_plugins


def get_command(command_name: str) -> Union[None, Command]:
    """Return the command of the given name. This assumes the command
    has already been validated as being one that exists.
    """

    _aliases = _cmd_tracker()

    command = _aliases.get(command_name)

    # If we already activated the command, just return it.
    if command and not command.is_dummy:
        return command

    # Find the real command from amongst the aliases.
    if command_name not in _builtin_commands:
        for alias_cmd, cmd_aliases in _builtin_aliases.items():
            if command_name in cmd_aliases:
                command_name = alias_cmd

    if command_name not in _builtin_commands:
        raise errors.CommandError(
            "Could not find command '{}'. You should always get an error from "
            "the argument parser, and never this one.".format(command_name))

    command_module, command_class = _builtin_commands[command_name]
    mod = importlib.import_module('.' + command_module, 'pavilion.commands')
    if not hasattr(mod, command_class):
        raise errors.CommandError(
            "Could not find class '{}' for builtin command '{}' in module '{}'. "
            "If you're seeing this, then a class was improperly registered in "
            "'pavilion.commands.__init__.py'."
            .format(command_class, command_name))

    command: Command = getattr(mod, command_class)()
    command.activate()

    return command


def load(*cmds: str):
    """Load the given commands. If no commands are given, load all commands."""

    if not cmds:
        cmds = _builtin_commands.keys()

    for cmd in cmds:
        get_command(cmd)
