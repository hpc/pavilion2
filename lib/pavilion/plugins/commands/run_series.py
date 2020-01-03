from pavilion import commands
from pavilion import arguments
from pavilion.test_config.setup import _find_config
from pavilion.test_config.file_format import SeriesConfigLoader


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

            run_cmd = commands.get_command('run')
            arg_parser = arguments.get_parser()

            sets = series_cfg['series']
            for set_name, set_info in sets.items():
                # create arguments
                args_list = ['run']
                args_list.extend(set_info['test_names'])
                args = arg_parser.parse_args(args_list)
                # call run command to run tests
                run_cmd.run(pav_cfg, args)

        return 0
