"""Start a series config defined test series."""

import errno
import sys

from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import series
from pavilion import series_config
from pavilion.errors import TestSeriesError, TestSeriesWarning
from .base_classes import Command, sub_cmd


class RunSeries(Command):
    """Command to kickoff series."""

    def __init__(self):
        super().__init__(
            name='series', sub_commands=True,
            description='Provides commands for running and working with test series.',
            short_help='Run/work with test series.',
        )

    def run(self, pav_cfg, args):
        """Run the show command's chosen sub-command."""

        return self._run_sub_command(pav_cfg, args)

    def _setup_arguments(self, parser):
        """Setup arguments for all sub commands."""

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="Series Status sub command.")

        run_p = subparsers.add_parser(
            'run',
            help="Run a series."
        )
        run_p.add_argument(
            'series_name', action='store',
            help="Series name."
        )
        run_p.add_argument(
            '--re-name', action='store',
            help="Ignore the series config file name, and rename the series to this."
        )
        run_p.add_argument(
            '-H', '--host', action='store', default=None,
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        run_p.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')
        run_p.add_argument(
            '-V', '--skip-verify', action='store_true', default=False,
            help="By default we load all the relevant configs. This can take some "
                 "time. Use this option to skip that step."
        )

        list_p = subparsers.add_parser(
            'list',
            aliases=['ls'],
            help="Show a list of recently run series.",
        )

        list_p.add_argument(
            'series', nargs='*',
            help="Specific series to show. Defaults to all your recent series on this cluster."
        )

        filters.add_series_filter_args(list_p)

    @sub_cmd()
    def _run_cmd(self, pav_cfg, args):
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
                output.fprint(self.errfile,
                              "Load error: {}".format(args.series_name), err,
                              color=output.RED)
                return errno.EINVAL

        if args.re_name is not None:
            series_cfg['name'] = str(args.re_name)

        # create brand-new series object
        try:
            series_obj = series.TestSeries(pav_cfg, config=series_cfg)
        except TestSeriesError as err:
            output.fprint(self.errfile, "Error creating test series '{}'"
                          .format(args.series_name), err, color=output.RED)
            return errno.EINVAL

        output.fprint(self.errfile, "Creating Series {}.\n".format(series_obj.name))

        # pav _series runs in background using subprocess
        try:
            series_obj.run_background()
        except TestSeriesError as err:
            output.fprint(self.errfile, "Error starting series '{}'"
                          .format(args.series_name), err, color=output.RED)
            return errno.EINVAL
        except TestSeriesWarning as err:
            output.fprint(self.errfile, err, color=output.YELLOW)

        output.fprint(self.outfile, "Started series {sid}.\n"
                                    "Run `pav status {sid}` to view status.\n"
                      .format(sid=series_obj.sid))

        if series_obj.pgid is not None:
            output.fprint(self.outfile, "PGID is {pgid}.\nTo kill, use `pav cancel {sid}`."
                          .format(sid=series_obj.sid, pgid=series_obj.pgid))
        else:
            output.fprint(self.errfile, "To cancel, use `kill -14 -s{pgid}"
                          .format(pgid=series_obj.pgid))

        return 0

    @sub_cmd('ls')
    def _list_cmd(self, pav_cfg, args):
        """List series."""

        matched_series = cmd_utils.arg_filtered_series(
            pav_cfg=pav_cfg, args=args, verbose=self.errfile)

        rows = []
        for ser_info in matched_series:
            sinfo_dict = ser_info.attr_dict()
            rows.append(sinfo_dict)

        fields = [
            'sid',
            'name',
            'status',
            'num_tests',
            'passed',
            'failed',
            'errors',
            'user',
            'sys_name',
            'complete',
            'status_when',
        ]

        output.draw_table(
            outfile=self.outfile,
            fields=fields,
            rows=rows,
            field_info={
                'num_tests': {'title': 'Tests'},
                'pfe': {'title': 'P/F/Err'},
                'sys_name': {'title': 'System'},
                'passed': {'title': 'P',
                           'transform': lambda t: output.ANSIString(t, output.GREEN)},
                'failed': {'title': 'F',
                           'transform': lambda t: output.ANSIString(t, output.RED)},
                'errors': {'title': 'E',
                           'transform': lambda t: output.ANSIString(t, output.YELLOW)},
                'status_when': {'title': 'Updated',
                                'transform': output.get_relative_timestamp},
            }
        )

        return 0
