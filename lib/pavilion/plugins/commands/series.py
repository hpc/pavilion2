"""Start a series config defined test series."""

from yaml_config import YAMLError, RequiredError
import errno

from pavilion import commands
from pavilion import series
from pavilion import series_config
from pavilion import output


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
        try:
            series_cfg = series_config.load_series_configs(pav_cfg,
                                                           args.series_name,
                                                           args.modes,
                                                           args.host)
        except (ValueError, KeyError, YAMLError, RequiredError) as err:
            output.fprint(
                "Error in series config file '{}': {}"
                .format(args.series_name, err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL

        # create brand-new series object
        try:
            series_obj = series.TestSeries(pav_cfg, series_config=series_cfg)
        except series.TestSeriesError as err:
            output.fprint(
                "Error creating test series '{}': {}"
                .format(args.series_name, err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL

        # pav _series runs in background using subprocess
        try:
            series_obj.run_background()
        except series.TestSeriesError as err:
            output.fprint(
                "Error starting series '{}': '{}'"
                .format(args.series_name, err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL
        except series.TestSeriesWarning as err:
            output.fprint(str(err.args[0]), color=output.YELLOW, file=self.errfile)

        output.fprint("Started series {sid}.\n"
                      "Run `pav status {sid}` to view status.\n"
                      .format(sid=series_obj.sid), file=self.outfile)

        if series_obj.pgid is not None:
            output.fprint(
                "PGID is {pgid}.\nTo kill, use `pav cancel {sid}`."
                .format(sid=series_obj.sid, pgid=series_obj.pgid),
                file=self.outfile)
        else:
            output.fprint(
                "To cancel, use `kill -14 -s{pgid}"
                .format(pgid=series_obj.pgid))

        return 0