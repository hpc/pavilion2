from argparse import ArgumentParser, Namespace

from pavilion import output
from pavilion.config import PavConfig
from pavilion.test_ids import TestID
from .base_classes import Command


class CDHelpCommand(Command):
    """This command exists solely to provide help information for the cd command, which due to
    technical reasons must be implemented in bash."""

    def __init__(self):
        super().__init__(
            "cd",
            "Change to the test directory of the test with the given ID.",
            short_help="Change to test directory")

    def _setup_arguments(self, parser: ArgumentParser) -> None:
        """Set up the arguments for the cd command."""

        parser.add_argument("test_id", type=TestID, help="test ID", nargs="?")

    def run(self, pav_cfg: PavConfig, args: Namespace) -> None:
        """Dummy method to run the cd command. This should never be run. Instead, pav cd
        invokes a bash function."""

        output.fprint(self.errfile,
                      "You must source the activate script before running the cd command.",
                      color=output.RED)
