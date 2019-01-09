from pavilion import arguments
from yapsy import IPlugin
import argparse
import logging

_COMMANDS = {}


def __reset():
    """Reset the command plugins. This is only to be used as part of unittests."""

    global _COMMANDS

    _COMMANDS = {}

    arguments._reset_parser()


class CommandError(RuntimeError):
    """The error type commands should raise for semi-expected errors."""
    pass


def add_command(command):
    """Add the given command instance to the dictionary of commands."""

    global _COMMANDS

    if command.name not in _COMMANDS:
        _COMMANDS[command.name] = command
    else:
        raise RuntimeError("Multiple commands of the same name are not allowed to exist. "
                           "command.{c1.name} found at both {c1.path} and {c2.path}."
                           .format(c1=_COMMANDS[command.name], c2=command))


def get_command(command_name):
    """Return the command of the given name.
    :rtype: Command
    """
    global _COMMANDS

    return _COMMANDS[command_name]


class Command(IPlugin.IPlugin):
    """Provides a pavilion command via a plugin."""

    def __init__(self, name, description):
        """Initialize this command. This should be overridden by subclasses, to set reasonable
        values. Multiple commands of the same name are not allowed to exist.

        :param name: The name of this command. Will be used as the subcommand name.
        :param description: The help text for this command.
        """
        super().__init__()

        self.logger = logging.getLogger('command.' + name)
        self.name = name
        self.description = description

    def _setup_arguments(self, parser):
        """Setup the commands arguments in the Pavilion argument parser.
        :param argparse.ArgumentParser parser:
        """
        pass

    def _setup_other(self):
        """Additional setup actions for this command at activiation time."""
        pass

    def activate(self):

        # Add the arguments for this command to the
        sub_parser = arguments.get_subparser()
        parser = sub_parser.add_parser(self.name, description=self.description)
        self._setup_arguments(parser)

        self._setup_other()

        add_command(self)

    def deactivate(self):
        raise RuntimeError("Command plugins cannot be deactiviated.")

    def run(self, pav_config, args):
        """This method should contain the
        :param pav_config: The pavilion configuration object.
        :param args: The parsed arguments for this command.
        :return: The return code of the command should denote success (0) or failure (not 0).
        """
        pass
