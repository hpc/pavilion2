import signal
import sys
from pavilion import commands
from pavilion import arguments
from pavilion import series
from pavilion import output
from pavilion.status_file import STATES
from pavilion.test_config.resolver import TestConfigResolver
from pavilion.test_config.file_format import SeriesConfigLoader


class AutoSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='_series',
            description='Run Series, but make this hidden.',
            short_help='Run complicated series, but make this hidden.',
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            'series_id', action='store',
            help="Series ID."
        )

    def run(self, pav_cfg, args):

        # load series obj
        series_obj = series.TestSeries.get_config_dep_from_id(pav_cfg,
                                                              args.series_id)

        # create doubly linked series stuff
        series_obj.create_set_graph()

        # call function to actually run series
        series_obj.run_series()

        return 0

