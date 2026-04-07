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

    def run(self, pav_cfg: PavConfig, args: Namespace) -> int:
        """Dummy method to display an error message if `pav cd` has not been activated.
        During normal use, this method will not be called, and `cd.sh` will be invoked instead."""

        output.fprint(self.errfile,
                      "The pav cd command must be activated before use. To activate, add the "
                      "following line to your activate.sh script, then source the script:\n\n"
                      "\tsource \"${PAV_CONFIG_DIR}/pav_src/lib/pavilion/commands/cd.sh\"\n\n"
                      "If you do not have an activate.sh script, you can generate one by running"
                      "the following command:\n\n"
                      "\tpav make-activate",
                      color=output.RED)

        return 1
