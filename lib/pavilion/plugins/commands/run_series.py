import subprocess

from pavilion import commands
from pavilion import arguments
from pavilion import series
from pavilion.output import fprint
from pavilion.test_config.resolver import TestConfigResolver
from pavilion.test_config.file_format import SeriesConfigLoader

from pavilion.output import dbg_print  # delete this


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

        # make series object
        series_obj = series.TestSeries(pav_cfg)

        temp_args = ['pav', '_auto_series', args.series,
                     '--series-id={}'.format(series_obj.id)]
        subprocess.Popen(temp_args, stdout=subprocess.DEVNULL)

        fprint("Started series {}. "
               "Run `watch pav status` to watch progress."
               .format(series_obj.id))

        return 0
