"""Runs a process that logs the results of a series' tests as tests complete."""

import sys
from typing import Optional

from pavilion import output
from pavilion import series
from pavilion.test_ids import SeriesID
from pavilion.result_logging import get_result_loggers
from pavilion.errors import TestSeriesError, ResultLoggerPluginError
from .base_classes import Command


class LogResults(Command):
    """Command to log the results of a series. Intended to be run in a child process of
    the series object's process."""

    def __init__(self):
        super().__init__(
            '_log_results',
            'Logs the results of a series\' tests as the tests complete.',
        )

    def _setup_arguments(self, parser: "ArgParser") -> None:
        """Sets up arguments for _log_series command. Only needs series ID."""

        parser.add_argument('series_id', type=SeriesID, action='store',
                            help="Series ID of the series whose tests will be logged.")
        parser.add_argument("-t", "--timeout", type=int, action="store", default=None,
                            help="Timeout value, in seconds, after which the result logging "
                                 "process will  terminate if no new tests complete. Defaults to "
                                 "no timeout."
        )

    def run(self, pav_cfg: "PavConfig", args: "Namespace") -> Optional[int]:
        """Loads series object from directory and runs series."""

        if args.timeout is not None and args.timeout <= 0:
            output.fprint(self.errfile,
                          "Result logger timeout must be a positive integer. "
                          f"Recieved: {args.timeout}.")

            return 1

        try:
            series_obj = series.TestSeries.load(
                pav_cfg,
                args.series_id,
                outfile=self.outfile)
        except TestSeriesError as err:
            output.fprint(self.errfile, f"Error loading series {args.series_id}: {err}",
                          color=output.RED)
            return 2

        try:
            result_loggers = get_result_loggers(pav_cfg, args.series_id, self.outfile)
        except ResultLoggerPluginError as err:
            output.fprint(self.errfile, f"Error making result loggers: {err}", color=output.RED)

            return 3

        try:
            # pylint: disable=protected-access
            series_obj._log_results(loggers=result_loggers, timeout=args.timeout)
        except TestSeriesError as err:
            output.fprint(self.errfile,
                          f"Error while logging results for series '{args.seriesid}': {err}.",
                          color=output.RED)
            return 4

        return 0
