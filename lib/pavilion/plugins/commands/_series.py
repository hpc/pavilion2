from pavilion import commands
from pavilion import series


class AutoSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='_series',
            description='Runs series in background.',
            short_help='Runs series in background.',
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            'series_id', action='store',
            help="Series ID."
        )

    def run(self, pav_cfg, args):

        # load series obj
        sid = 's' + args.series_id
        series_obj = series.TestSeries.from_id(pav_cfg, sid)

        # call function to actually run series
        series_obj.run_series()

        return 0

