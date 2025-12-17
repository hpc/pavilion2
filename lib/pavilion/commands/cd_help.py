from arpgarse import ArgParser

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

    def _setup_arguments(self, parser: ArgParser) -> None:
        """Set up the arguments for the cd command."""

        parser.add_argument("test_id", type=TestID, help="test ID", nargs="?")