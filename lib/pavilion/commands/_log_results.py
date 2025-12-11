"""Runs a process that logs the results of a series' tests as tests complete."""

import sys
from typing import Optional

from pavilion import output
from pavilion import series
from pavilion.test_ids import SeriesID
from pavilion.errors import TestSeriesError
from .base_classes import Command


class LogResults(Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            '_log_results',
            'Logs the results of a series\' tests as the tests complete.',
        )

    def _setup_arguments(self, parser: "ArgParser") -> None:
        """Sets up arguments for _log_series command. Only needs series ID."""

        parser.add_argument(
            'series_id', type=SeriesID, action='store',
            help="Series ID."
        )

    def run(self, pav_cfg: "PavConfig", args: "Namespace") -> Optional[int]:
        """Loads series object from directory and runs series."""

        try:
            series_obj = series.TestSeries.load(
                pav_cfg,
                args.series_id,
                outfile=self.outfile)
        except TestSeriesError as err:
            output.fprint(self.outfile, "Error in _log_results cmd.", err)
            sys.exit(1)
        try:
            series_obj.log_results()
        except TestSeriesError as err:
            output.fprint(self.errfile,
                "Error while logging results for series '{}'.".format(args.series_id))
            output.fprint(self.errfile, err.pformat())

        return 0
