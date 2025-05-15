""""Base classes and methods for Command plugins"""

# pylint: disable=W0603

import argparse
import errno
import inspect
import io
import logging
import sys
from typing import List

from pavilion.utils import WrappedFormatter
from pavilion import output
from yapsy import IPlugin

_COMMANDS = {}
_ALIASES = {}


def __reset():
    """Reset the command plugins. This is only to be used as part of
    unittests."""

    global _COMMANDS
    _COMMANDS = {}
    global _ALIASES
    _ALIASES = {}


def add_command(command):
    """Add the given command instance to the dictionary of commands.

:param Command command: The command object to add
"""

    global _COMMANDS
    global _ALIASES

    existing_cmd = _COMMANDS.get(command.name)
    if existing_cmd is not None and not existing_cmd.is_dummy:
        raise RuntimeError(
            "Multiple commands of the same name are not allowed to exist. "
            "command.{c1.name} found at both {c1.path} and {c2.path}."
            .format(c1=existing_cmd, c2=command))

    _COMMANDS[command.name] = command

    for name in command.aliases:
        _ALIASES[name] = command

def cmd_tracker():
    """Return the command tracking object."""

    # We can't just import this - it gets pointed at different objects over time.
    return _ALIASES


def setup_arguments(parser: argparse.ArgumentParser):
    """Setup arguments for all known commands."""

    global _COMMANDS

    # This is dynamically added to the parser at creation time.
    sub_parser = parser.cmd_sub_parser

    for command in _COMMANDS.values():
        command.setup_arguments(sub_parser)


class Command(IPlugin.IPlugin):
    """Provides a pavilion command via a plugin.

    :ivar argparse.ArgumentParser parser: The plugin's argument parser object.
    """

    def __init__(self, name, description, short_help=None, aliases=None,
                 sub_commands=False, formatter_class=None, is_dummy=False):
        """Initialize this command. This should be overridden by subclasses, to
        set reasonable values. Multiple commands of the same name are not
        allowed to exist.

        :param name: The name of this command. Will be used as the subcommand
            name.
        :param str description: The full description and help header for this
            command. Displayed with 'pav <cmd> --help'.
        :param str short_help: A short description of the command displayed
            when doing a 'pav --help'. If this is None, the command won't
            be listed.
        :param list aliases: A list of aliases for the command.
        :param bool sub_commands: Enable the standardized way of adding sub
            commands.
        :param is_dummy: Set to true for dummy commands (used as placeholders
            for builtin commands).
        """
        super().__init__()

        if aliases is None:
            aliases = []

        aliases = [name] + aliases.copy()

        self.logger = logging.getLogger('command.' + name)
        self.name = name
        self.file = inspect.getfile(self.__class__)
        self.description = description
        self.short_help = short_help
        self.aliases = aliases
        self.is_dummy = is_dummy
        if formatter_class:
            self.formatter_class = formatter_class
        else:
            self.formatter_class = WrappedFormatter

        # These are to allow tests to redirect output as needed.
        self.outfile = sys.stdout
        self.errfile = sys.stderr

        self.sub_cmds = {}
        if sub_commands:
            self._inventory_sub_commands()

        self._parser = None

        # This is used primarily by the run command,
        self.last_series = None
        self.last_tests = []  # type: List

    def _inventory_sub_commands(self):
        """Find all the sub commands and populate the sub_cmds dict."""

        # Walk the class dictionary and add any functions with aliases
        # to our dict of commands under each listed alias.
        for func in self.__class__.__dict__.values():

            # Add alias names
            if callable(func) and hasattr(func, 'aliases'):
                # Add the name from the function.
                name = func.__name__
                if name.endswith('_cmd'):
                    name = name[:-4]
                name = name.lstrip('_')
                self.sub_cmds[name] = func

                for alias in func.aliases:
                    self.sub_cmds[alias] = func

    def setup_arguments(self, sub_parser):
        """Add arguments for this command to the give argparse sub_parser."""

        kwargs = {
            'aliases': self.aliases,
            'description': self.description,
            'add_help': not self.is_dummy,
        }
        if self.short_help is not None:
            kwargs['help'] = self.short_help
            kwargs['formatter_class'] = WrappedFormatter


        # Save the argument parser, as it can come in handy.
        self._parser = sub_parser.add_parser(self.name, **kwargs)

        if self.is_dummy:
            self._parser.add_argument('--help', '-h', action='store_true')

        self._setup_arguments(self._parser)

    def _setup_arguments(self, parser):
        """Setup the commands arguments in the Pavilion argument parser. This
    is handed a pre-created sub-command parser for this command. Simply
    add arguments to it like you would a base parser. ::

        parser.add_arguemnt('-x', '--extra',
                            action='store_true',
                            help="Add extra stuff.")

    :param argparse.ArgumentParser parser: The parser object."""

    def _setup_other(self):
        """Additional setup actions for this command at activation time.
        The base version of this does nothing.."""

    def activate(self):
        """The Yapsy plugin system calls this to setup the plugin. In this
case that includes:

- Adding the command's sub-command arguments to the general pavilion argument
  parser.
- Running the _setup_other method.
- Adding the command to Pavilion's known commands.
"""
        self._setup_other()

        add_command(self)

    def deactivate(self):
        """You can't deactivate commands."""
        raise RuntimeError("Command plugins cannot be deactivated.")

    def run(self, pav_cfg, args):
        """Override this method with your command's code.

:param pav_cfg: The pavilion configuration object.
:param argparse.Namespace args: The parsed arguments for pavilion.
:return: The return code of the command should denote success (0) or
    failure (not 0).
"""
        raise NotImplementedError(
            "Command plugins must override the 'run' method.")

    def _run_sub_command(self, pav_cfg, args):
        """Find and run the subcommand."""

        cmd_name = args.sub_cmd

        if cmd_name is None:
            output.fprint(self.errfile, "You must provide a sub command.",
                          color=output.RED)
            self._parser.print_help(file=self.errfile)
            return errno.EINVAL

        if cmd_name not in self.sub_cmds:
            raise RuntimeError("Invalid sub-cmd '{}'".format(cmd_name))

        cmd_result = self.sub_cmds[cmd_name](self, pav_cfg, args)
        return 0 if cmd_result is None else cmd_result

    def __repr__(self):
        return '<{} from file {} named {}>'.format(
            self.__class__.__name__,
            self.file,
            self.name
        )

    def silence(self):
        """Convert the command to use string IO for its output and error
        output."""
        self.outfile = io.StringIO()
        self.errfile = io.StringIO()

    def clear_output(self):
        """Reset the output io buffers for this command."""

        if not isinstance(self.outfile, io.StringIO):
            raise RuntimeError("Only silenced commands can be cleared.")

        self.outfile.seek(0)
        data = self.outfile.read()
        self.outfile.seek(0)
        self.outfile.truncate(0)

        self.errfile.seek(0)
        err_data = self.errfile.read()
        self.errfile.seek(0)
        self.errfile.truncate(0)

        return data, err_data

    @property
    def path(self):
        """The path to the object that defined this instance."""

        if self.__class__ is Command:
            return '<builtin>'
        else:
            return inspect.getfile(self.__class__)


def sub_cmd(*aliases):
    """Tag this given function as a sub_cmd, and record its aliases."""

    def tag_aliases(func):
        """Attach all the aliases to the given function, but return the
        function itself. The function name, absent leading underscores and
        without a trailing '_cmd', is added by default."""
        name = func.__name__

        while name.startswith('_'):
            name = name[1:]

        if name.endswith('_cmd'):
            name = name[:-4]

        func.aliases = [name]
        for alias in aliases:
            func.aliases.append(alias)

        return func

    return tag_aliases
