from pavilion import commands
from pavilion import series
from pavilion import series_config


class RunSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='series',
            description='Runs a series that is defined/configured from a test '
                        'series file.',
            short_help='Run a predefined series.',
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            'series_name', action='store',
            help="Series name."
        )
        parser.add_argument(
            '-H', '--host', action='store', default=None,
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')

    def run(self, pav_cfg, args):
        """Gets called when `pav series <series_name>` is executed. """

        # load series and test files
        series_cfg = series_config.load_series_configs(pav_cfg,
                                                       args.series_name,
                                                       args.modes,
                                                       args.host)

        # create brand-new series object
        series_obj = series.TestSeries(pav_cfg,
                                       series_config=series_cfg,
                                       outfile=self.outfile,
                                       errfile=self.errfile)

        # pav _series runs in background using subprocess
        series_obj.run_series_background()

        return
