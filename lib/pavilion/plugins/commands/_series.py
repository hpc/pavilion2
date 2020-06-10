import signal
import sys
from pavilion import commands
from pavilion import arguments
from pavilion import series
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
            'series', action='store',
            help="Suite name."
        )
        parser.add_argument(
            '--series-id',
            help='Provide series ID if test is already part of a series.'
        )

    def run(self, pav_cfg, args):

        self.make_series_man(pav_cfg, args)

        return 0

    # pylint: disable=no-self-use
    def make_series_man(self, pav_cfg, args):

        series_name = args.series

        series_config_loader = SeriesConfigLoader()

        # pylint: disable=protected-access
        tsr = TestConfigResolver(pav_cfg)
        series_path = tsr._find_config('series', series_name)

        with series_path.open() as series_file:
            if not args.series_id:
                series_obj = series.TestSeries(pav_cfg)
            else:
                series_obj = series.TestSeries.from_id(pav_cfg, args.series_id)

            series_cfg = series_config_loader.load(series_file)
            if series_cfg['ordered'] in ['True', 'true']:
                ser_keys = list(series_cfg['series'].keys())
                for ser_idx in range(len(ser_keys)-1):
                    temp_depends_on = series_cfg['series'][ser_keys[
                        ser_idx+1]]['depends_on']
                    if ser_keys[ser_idx] not in temp_depends_on:
                        temp_depends_on.append(ser_keys[ser_idx])

            series_man = series.SeriesManager(pav_cfg,
                                              series_obj,
                                              series_cfg)
            return series_man

