"""Runs a process that manages series and their dependencies."""

from pavilion import commands
from pavilion import series


class AutoSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='_series',
            description='Runs an existing series object.',
            short_help='Runs an existing series object.',
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
        series_obj = series.TestSeries.from_id(
            pav_cfg, args.series_id,
            outfile=self.outfile, errfile=self.errfile)

        # call function to actually run series
        series_obj.run_series()

        return 0
