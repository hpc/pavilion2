from argparse import ArgumentParser, Namespace

from pavilion import output
from pavilion.config import PavConfig
from pavilion.test_ids import TestID
from .base_classes import Command


class CDHelpCommand(Command):
    """Display help and usage information for the `cd` command, which must be activated from the
    `cd.sh` script."""

    def __init__(self):
        super().__init__(
            "cd",
            "Change to the test run directory of the test with the given ID."
            short_help="Change to test run directory")

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        """Set up the arguments for the cd command."""

        parser.add_argument("test_id", type=TestID,
                            help="Test ID of the test run directory to change to. "
                                 "If no ID is given, defaults to the most recent test.",
                            nargs="?")

    def run(self, pav_cfg: PavConfig, args: Namespace) -> None:
        """Dummy method to run the cd command. This should never be run. Instead, pav cd
        invokes a bash function."""

        output.fprint(self.errfile,
                      "You must source the activate script before running the cd command.",
                      color=output.RED)
