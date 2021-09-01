"""Runs a process that manages series and their dependencies."""

import signal
import sys

from pavilion import commands
from pavilion import output
from pavilion import series


class AutoSeries(commands.Command):
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
            series_obj = series.TestSeries.load(pav_cfg, args.series_id)
        except series.TestSeriesError as err:
            output.fprint("Error in _series cmd: {}".format(err.args[0]))
            sys.exit(1)

        # handles SIGTERM (15) signal
        def sigterm_handler(_signals, _frame_type):
            """Calls cancel_series and exists."""

            series_obj.cancel(message="Series killed by SIGTERM.")
            sys.exit(1)

        signal.signal(signal.SIGTERM, sigterm_handler)

        try:
            # call function to actually run series
            series_obj.run(outfile=self.outfile)
        except series.TestSeriesError as err:
            output.fprint("Error while running series '{}'. {}"
                          .format(args.series, err.args[0]),
                          file=self.errfile)

        return 0
