from pavilion import commands
from pavilion import arguments
from pavilion import series
from pavilion.test_config.resolver import TestConfigResolver
from pavilion.test_config.file_format import SeriesConfigLoader

from pavilion.output import dbg_print


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

        # pylint: disable=W0212
        tsr = TestConfigResolver(pav_cfg)
        series_path = tsr._find_config('series', series_name)

        with series_path.open() as series_file:
            series_cfg = series_config_loader.load(series_file)

            run_cmd = commands.get_command('run')
            arg_parser = arguments.get_parser()

            series_obj = series.TestSeries(pav_cfg)

            # get universal modes
            universal_modes = series_cfg['modes']

            # set up series
            sets = series_cfg['series']
            for set_name, set_info in sets.items():

                # get all appropriate modes
                set_modes = set_info['modes']
                all_modes = universal_modes + set_modes

                # create arguments
                # pylint: disable=W0212
                args_list = ['run', '--series-id={}'.format(series_obj.id)]
                for mode in all_modes:
                    args_list.append('-m{}'.format(mode))
                args_list.extend(set_info['test_names'])
                args = arg_parser.parse_args(args_list)

                # call run command to run tests
                run_cmd.run(pav_cfg, args)

        return 0
