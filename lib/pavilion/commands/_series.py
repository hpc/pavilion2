"""Runs a process that manages series and their dependencies."""

import signal
import sys

from pavilion import output
from pavilion import series
from pavilion.errors import TestSeriesError
from .base_classes import Command


class AutoSeries(Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            '_series',
            'Runs an existing series object.',
        )

    def _setup_arguments(self, parser):
        """Sets up arguments for _series command. Only needs series ID."""

        parser.add_argument(
            'series_id', action='store',
            help="Series ID."
        )

    def run(self, pav_cfg, args):
        """Loads series object from directory and runs series."""

        # load series obj
        try:
            series_obj = series.TestSeries.load(
                pav_cfg,
                args.series_id,
                outfile=self.outfile)
        except TestSeriesError as err:
            output.fprint(sys.stdout, "Error in _series cmd.", err)
            sys.exit(1)
        try:
            # call function to actually run series
            series_obj.run()
        except TestSeriesError as err:
            output.fprint(self.errfile, "Error while running series '{}'.".format(args.series_id))
            output.fprint(self.errfile, err.pformat(args.show_tracebacks))

        return 0
