# Base classes and methods for Command plugins

# pylint: disable=W0603

import inspect
import logging
import sys

from pavilion import arguments
from yapsy import IPlugin

_COMMANDS = {}


def __reset():
    """Reset the command plugins. This is only to be used as part of
    unittests."""

    global _COMMANDS

    _COMMANDS = {}

    arguments.reset_parser()


class CommandError(RuntimeError):
    """The error type commands should raise for semi-expected errors."""


def add_command(command):
    """Add the given command instance to the dictionary of commands.

:param Command command: The command object to add
"""

    global _COMMANDS

    if command.name not in _COMMANDS:
        _COMMANDS[command.name] = command
    else:
        raise RuntimeError(
            "Multiple commands of the same name are not allowed to exist. "
            "command.{c1.name} found at both {c1.path} and {c2.path}."
            .format(c1=_COMMANDS[command.name], c2=command))


def get_command(command_name):
    """Return the command of the given name.

    :param str command_name: The name of the command to search for.
    :rtype: Command
    """
    global _COMMANDS

    return _COMMANDS[command_name]


class Command(IPlugin.IPlugin):
    """Provides a pavilion command via a plugin."""

    def __init__(self, name, description, short_help=None, aliases=None):
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
        """
        super().__init__()

        self.logger = logging.getLogger('command.' + name)
        self.name = name
        self.file = inspect.getfile(self.__class__)
        self.description = description
        self.short_help = short_help
        self._aliases = aliases if aliases is not None else []

        # These are to allow tests to redirect output as needed.
        self.outfile = sys.stdout
        self.errfile = sys.stderr

    def _setup_arguments(self, parser):
        """Setup the commands arguments in the Pavilion argument parser.

        :param argparse.ArgumentParser parser:
        """

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

        # Add the arguments for this command to the
        sub_parser = arguments.get_subparser()

        # A add the short help, or not. A quirk of argparse is that if 'help'
        # is set, the subcommand is listed regardless of whether the
        # help is None. If we don't want that, we have to init without 'help'.
        if self.short_help is None:
            parser = sub_parser.add_parser(self.name,
                                           aliases=self._aliases,
                                           description=self.description)
        else:
            parser = sub_parser.add_parser(self.name,
                                           aliases=self._aliases,
                                           description=self.description,
                                           help=self.short_help)

        self._setup_arguments(parser)

        self._setup_other()

        add_command(self)

    def deactivate(self):
        raise RuntimeError("Command plugins cannot be deactivated.")

    def run(self, pav_cfg, args, out_file=sys.stdout, err_file=sys.stderr):
        """Override this method with your command's code.

:param pav_cfg: The pavilion configuration object.
:param args: The parsed arguments for pavilion.
:param out_file: Where to write output for this command.
:param err_file: Where to write err output for this command.
:return: The return code of the command should denote success (0) or
    failure (not 0).
"""

        raise NotImplementedError(
            "Command plugins must override the 'run' method.")

    def __repr__(self):
        return '<{} from file {} named {}>'.format(
            self.__class__.__name__,
            self.file,
            self.name
        )
