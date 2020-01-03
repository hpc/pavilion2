from pavilion import commands
from pavilion.test_config.setup import _find_config
from pavilion.test_config.file_format import SeriesConfigLoader

from pavilion.output import dbg_print
import pprint

class RunSeries(commands.Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='run_series',
            description='Run Series.',
            short_help='Run complicated series.',
        )

    def _setup_arguments(self, parser):

        parser.add_argument(
            'series', action='store',
            help="Suite name."
        )

    def run(self, pav_cfg, args):

        series_name = args.series

        series_config_loader = SeriesConfigLoader()

        series_path = _find_config(pav_cfg, 'series', series_name)

        with series_path.open() as series_file:
            series_cfg = series_config_loader.load(series_file)
            # series_cfg = series_config_loader.load_raw(series_file)
            pp = pprint.PrettyPrinter(indent=2)
            pp.pprint(series_cfg)

        return 0