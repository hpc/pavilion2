"""This file contains common 'enum' constants."""

import enum

class Verbose(enum.Enum):
    """Verbosity levels for test series."""

    # Minimal status output.
    QUIET = 0

    # Regular status updates that overwrite previous lines.
    DYNAMIC = 1

    # Full final status for every item, but no dynamic output
    HIGH = 2

    # Maximum status updates for each item (but no dynamic)
    MAX = 3

