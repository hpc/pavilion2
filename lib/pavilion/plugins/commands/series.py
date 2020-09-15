import subprocess
import os
import json

from pavilion import commands
from pavilion import arguments
from pavilion import series
from pavilion import output
from pavilion import series_config
from pavilion.output import fprint
from pavilion.test_config.resolver import TestConfigResolver
from pavilion.series_config.file_format import SeriesConfigLoader


class RunSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='series',
            description='Run Series.',
            short_help='Run complicated series.',
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            'series_name', action='store',
            help="Series name."
        )
        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')

    def run(self, pav_cfg, args):

        # load series and test files
        series_cfg = series_config.load_series_configs(pav_cfg,
                                                       args.series_name,
                                                       args.modes,
                                                       args.host)

        series_obj = series.TestSeries(pav_cfg,
                                       series_config=series_cfg)

        series_path = series_obj.path
        series_id = series_obj._id

        # pav _series runs in background using subprocess
        series_proc = series_obj.run_series_background()

        return

