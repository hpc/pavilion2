"""Start a series config defined test series."""

import errno
import sys
from typing import List

from pavilion import cancel_utils
from pavilion import config
from pavilion import cmd_utils
from pavilion import filters
from pavilion import output
from pavilion import series
from pavilion import series_config
from pavilion import sys_vars
from pavilion import utils
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

        # Useful for testing this command. Populated by the run sub command.
        self.last_run_series: Union[series.TestSeries, None] = None

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
            aliases=['ls', 'status'],
            help="Show a list of recently run series.",
        )

        list_p.add_argument(
            'series', nargs='*',
            help="Specific series to show. Defaults to all your recent series on this cluster."
        )

        filters.add_series_filter_args(list_p)

        history_p = subparsers.add_parser(
            'history',
            help="Give the status history of the given series.")
        history_p.add_argument('--text', '-t', action='store_true', default=False,
                               help="Print plaintext, rather than a table.")
        history_p.add_argument('series', default='last', nargs='?',
                               help="The series to print status history for.")

        cancel_p = subparsers.add_parser(
            'cancel',
            help="Cancel a series or series. Defaults to the your last series on this system.")
        filters.add_series_filter_args(cancel_p, sort_keys=[], disable_opts=['sys-name'])
        cancel_p.add_argument('series', nargs='*', help="One or more series to cancel")

        set_status_p = subparsers.add_parser(
            'sets',
            help="Show the status of the test sets for a given series.")
        set_status_p.add_argument('--merge-repeats', '-m', default=False, action='store_true',
                                  help='Merge data from all repeats of each set.')
        set_status_p.add_argument('series', default='last', nargs='?',
                                  help='The series to print the sets for.')

    def _find_series(self, pav_cfg, series_name):

        if series_name == 'last':
            ser = cmd_utils.load_last_series(pav_cfg, self.errfile)
        else:
            try:
                ser = series.TestSeries.load(pav_cfg, series_name)
            except series.TestSeriesError as err:
                output.fprint(self.errfile,
                              "Could not load given series '{}': {}"
                              .format(series_name, err.args[0]))
                return None

        return ser

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

                output.fprint(self.errfile, err.pformat(), color=output.RED)
                return errno.EINVAL

        if args.re_name is not None:
            series_cfg['name'] = str(args.re_name)

        # create brand-new series object
        try:
            series_obj = series.TestSeries(pav_cfg, series_cfg=series_cfg)
        except TestSeriesError as err:
            output.fprint(self.errfile, "Error creating test series '{}'"
                          .format(args.series_name), err, color=output.RED)
            return errno.EINVAL

        output.fprint(self.errfile, "Created Test Series {}.".format(series_obj.name))

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

        self.last_run_series = series_obj

        return 0

    @sub_cmd('ls', 'status', 'list')
    def _list_cmd(self, pav_cfg, args):
        """List series."""

        matched_series = cmd_utils.arg_filtered_series(
            pav_cfg=pav_cfg, args=args, verbose=self.errfile)

        rows = [ser.attr_dict() for ser in matched_series]

        fields = [
            'sid',
            'name',
            'status',
            'num_tests',
            'scheduled',
            'running',
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
                'sys_name': {'title': 'System'},
                'scheduled': {'title': 'Sch',
                              'transform': lambda t: output.ANSIString(t, output.CYAN)},
                'running': {'title': 'Run',
                              'transform': lambda t: output.ANSIString(t, output.MAGENTA)},
                'passed': {'title': 'Pass',
                           'transform': lambda t: output.ANSIString(t, output.GREEN)},
                'failed': {'title': 'Fail',
                           'transform': lambda t: output.ANSIString(t, output.RED)},
                'errors': {'title': 'Err',
                           'transform': lambda t: output.ANSIString(t, output.YELLOW)},
                'status_when': {'title': 'Updated',
                                'transform': output.get_relative_timestamp},
            }
        )

        return 0

    @sub_cmd('sets', 'set', 'set_status')
    def _list_sets_cmd(self, pav_cfg, args):
        """Display a series by test set."""

        ser = self._find_series(pav_cfg, args.series)
        if ser is None:
            return errno.EINVAL

        rows = []

        if args.merge_repeats:
            fields = ['name', 'iterations', 'complete', 'created', 'num_tests', 'scheduled',
                      'running', 'passed', 'failed', 'errors']
        else:
            fields = ['repeat', 'name', 'complete', 'created', 'num_tests', 'scheduled', 'running', 'passed',
                      'failed', 'errors']

        sets = {}

        for test_set in ser.test_set_dirs():
            test_set = test_set.name

            set_info = series.TestSetInfo(pav_cfg, ser.path, test_set)

            if args.merge_repeats:
                name = set_info.name
                if name in sets:
                    sets[name] = self._merge_sets(sets[name], set_info, fields)
                else:
                    sets[name] = set_info
            else:
                sets[test_set] = set_info

        sets = list(sets.values())
        sets.sort(key = lambda f: f['created'])

        output.draw_table(
            outfile=self.outfile,
            fields=fields,
            rows=sets,
            field_info={
                'repeat': {'title': 'Iter'},
                'iterations': {'title': 'Sets'},
                'complete': {'title': 'Done'},
                'num_tests': {'title': 'Tests'},
                'scheduled': {'title': 'Sch',
                              'transform': lambda t: output.ANSIString(t, output.CYAN)},
                'running': {'title': 'Run',
                              'transform': lambda t: output.ANSIString(t, output.MAGENTA)},
                'passed': {'title': 'Pass',
                           'transform': lambda t: output.ANSIString(t, output.GREEN)},
                'failed': {'title': 'Fail',
                           'transform': lambda t: output.ANSIString(t, output.RED)},
                'errors': {'title': 'Err',
                           'transform': lambda t: output.ANSIString(t, output.YELLOW)},
                'created': {'transform': output.get_relative_timestamp}
            })



    def _merge_sets(self, set1: dict, set2: dict, keys: List[str]) -> dict:
        """Merge to test set info dicts together, only looking at the given keys."""

        newdict = {}
        for key in keys:
            if key == 'iterations':
                # Keep track of the total combined iterations.
                newdict[key] = sum([set1.get(key, 1), set2.get(key, 1)])
            else:
                val1 = set1[key]
                val2 = set2[key]

                if key == 'created':
                    newdict[key] = min([val1, val2])
                elif isinstance(val1, (int, float)):
                    newdict[key] = val1 + val2
                elif isinstance(val1, bool):
                    newdict[key] = val1 and val2
                elif isinstance(val1, str):
                    newdict[key] = val1
                else:
                    newdict[key] = ''

        return newdict

    @sub_cmd()
    def _history_cmd(self, pav_cfg: config.PavConfig, args):
        """Print the full status history for a series."""

        if args.series == 'last':
            ser = cmd_utils.load_last_series(pav_cfg, self.errfile)
            if ser is None:
                return errno.EINVAL
        else:
            try:
                ser = series.TestSeries.load(pav_cfg, args.series)
            except series.TestSeriesError as err:
                output.fprint(self.errfile,
                              "Could not load given series '{}': {}"
                              .format(args.series, err.args[0]))
                return errno.EINVAL

        if args.text:
            for status in ser.status.history():
                output.fprint(self.outfile,
                              "{} {} {}".format(status.state, status.when, status.note))
            return 0
        else:
            output.draw_table(
                outfile=self.outfile,
                fields=['state', 'when', 'note'],
                rows=[status.as_dict() for status in ser.status.history()],
                field_info={
                    'when': {
                        'transform': output.get_relative_timestamp,
                    }
                }
            )

    @sub_cmd()
    def _cancel_cmd(self, pav_cfg, args):
        """Cancel all series found given the arguments."""

        args.user = args.user or utils.get_login()
        args.sys_name = sys_vars.get_vars(defer=True).get('sys_name')

        series_info = cmd_utils.arg_filtered_series(pav_cfg, args, verbose=self.errfile)
        output.fprint(self.outfile, "Found {} series to cancel.".format(len(series_info)))

        chosen_series = []
        for ser in series_info:
            try:
                loaded_ser = series.TestSeries.load(pav_cfg, ser.sid)
                chosen_series.append(loaded_ser)
            except series.TestSeriesError as err:
                output.fprint(self.errfile,
                              "Could not load found series '{}': {}"
                              .format(ser.sid, err.args[0]))

        tests_to_cancel = []
        for ser in chosen_series:
            # We'll cancel the tests verbosely.
            ser.cancel(message="By user {}".format(args.user), cancel_tests=False)
            output.fprint(self.outfile, "Series {} cancelled.".format(ser.sid))

            if ser.tests:
                tests_to_cancel.extend(ser.tests.values())

        output.fprint(self.outfile, "\nCancelling individual tests in each series.")

        return cancel_utils.cancel_tests(pav_cfg, tests_to_cancel, self.outfile)
