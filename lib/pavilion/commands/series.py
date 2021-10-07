"""Start a series config defined test series."""

import errno

import pavilion.series.errors
from pavilion import output
from pavilion import series
from pavilion import series_config
from .base_classes import Command


class RunSeries(Command):
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
        parser.add_argument(
            '-V', '--skip-verify', action='store_true', default=False,
            help="By default we load all the relevant configs. This can take some "
                 "time. Use this option to skip that step."
        )

    def run(self, pav_cfg, args):
        """Gets called when `pav series <series_name>` is executed. """

        if args.skip_verify:
            series_cfg = series_config.verify_configs(pav_cfg, args.series_name)
        else:
            # load series and test files
            try:
                # Pre-verify that all the series, tests, modes, and hosts exist.
                series_cfg = series_config.verify_configs(pav_cfg,
                                                          args.series_name,
                                                          host=args.host,
                                                          modes=args.modes)
            except series_config.SeriesConfigError as err:
                output.fprint(
                    "Load error: {}".format(args.series_name, err.args[0]),
                    color=output.RED, file=self.errfile)
                return errno.EINVAL

        # create brand-new series object
        try:
            series_obj = series.TestSeries(pav_cfg, config=series_cfg)
        except pavilion.series.errors.TestSeriesError as err:
            output.fprint(
                "Error creating test series '{}': {}"
                .format(args.series_name, err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL

        # pav _series runs in background using subprocess
        try:
            series_obj.run_background()
        except pavilion.series.errors.TestSeriesError as err:
            output.fprint(
                "Error starting series '{}': '{}'"
                .format(args.series_name, err.args[0]),
                color=output.RED, file=self.errfile)
            return errno.EINVAL
        except pavilion.series.errors.TestSeriesWarning as err:
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
