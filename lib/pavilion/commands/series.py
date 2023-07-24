"""Start a series config defined test series."""

import argparse
import errno
import sys
from typing import List

from pavilion import arguments
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
            description='Provides commands for running and working with test series.\n'
                        '  For information on configuring series, run `pav show series_config`.\n'
                        '  To see series log output, run `pav log series <series_id>`',
            short_help='Run/work with test series.',
        )

        # Useful for testing this command. Populated by the run sub command.
        self.last_run_series: Union[series.TestSeries, None] = None

    def run(self, pav_cfg, args):
        """Run the show command's chosen sub-command."""

        return self._run_sub_command(pav_cfg, args)

    LIST_ALIASES = ['ls', 'status']
    SETS_ALIASES = ['set_status', 'test_sets', 'set']
    STATE_ALIASES = ['state', 'states']

    def _setup_arguments(self, parser):
        """Setup arguments for all sub commands."""

        subparsers = parser.add_subparsers(
            dest="sub_cmd",
            help="Series Status sub command.")

        cancel_p = subparsers.add_parser(
            'cancel',
            help="Cancel a series or series. Defaults to the your last series on this system.")
        filters.add_series_filter_args(cancel_p, sort_keys=[], disable_opts=['sys-name'])
        cancel_p.add_argument('series', nargs='*', help="One or more series to cancel")

        list_p = subparsers.add_parser(
            'list',
            aliases=self.LIST_ALIASES,
            help="Show a list of recently run series.\n\n"
                 "Fields: \n"
                 "  - Sid       - The series id\n"
                 "  - Name      - The series name\n"
                 "  - State     - Most recent series state.\n"
                 "  - Tests     - Total tests created under this series.\n"
                 "  - Sched     - Number of tests in a 'scheduled' state.\n"
                 "  - Run       - Number of tests in a 'running' state.\n"
                 "  - Err       - Number of errors encountered by the series and tests.\n"
                 "                (see `pav series history --errors` series errors and \n"
                 "                     `pav status <series_id>` for test errors)\n"
                 "  - Pass      - Number of completed tests that passed.\n"
                 "  - Fail      - Number of completed tests that failed.\n"
                 "  - User      - Who started the series.\n"
                 "  - System    - The system the series ran on.\n"
                 "  - Complete  - Whether the series itself is complete.\n"
                 "                  (All tests created and complete).\n"
                 "  - Updated   - Last series status update.\n",
            formatter_class=arguments.WrappedFormatter)

        list_p.add_argument(
            'series', nargs='*',
            help="Specific series to show. Defaults to all your recent series on this cluster.",
        )
        filters.add_series_filter_args(list_p)

        run_p = subparsers.add_parser(
            'run',
            help="Run a series."
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
            '-c', dest='overrides', action='append', default=[],
            help='Overrides for specific configuration options. These are '
                 'gathered used as a final set of overrides before the '
                 'configs are resolved. They should take the form '
                 '\'key=value\', where key is the dot separated key name, '
                 'and value is a json object. Example: `-c schedule.nodes=23`')
        run_p.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')

        run_p.add_argument(
            '-V', '--skip-verify', action='store_true', default=False,
            help="By default we load all the relevant configs. This can take some "
                 "time. Use this option to skip that step."
        )
        run_p.add_argument(
            'series_name', action='store', nargs="?",
            help="Series name."
        )

        set_status_p = subparsers.add_parser(
            'sets',
            aliases=self.SETS_ALIASES,
            help="Show the status of the test sets for a given series. Columns are as per "
                 "`pav series status`")
        set_status_p.add_argument('--merge-repeats', '-m', default=False, action='store_true',
                                  help='Merge data from all repeats of each set.')
        set_status_p.add_argument('series', default='last', nargs='?',
                                  help='The series to print the sets for.')

        state_p = subparsers.add_parser(
            'state_history',
            aliases=self.STATE_ALIASES,
            help="Give the state history of the given series.")
        state_p.add_argument('--text', '-t', action='store_true', default=False,
                             help="Print plaintext, rather than a table.")
        state_p_filter_args = state_p.add_mutually_exclusive_group()
        state_p_filter_args.add_argument(
            '--errors', action='store_true', default=False,
            help="List only encountered errors.")
        state_p_filter_args.add_argument(
            '--skipped', action='store_true', default=False,
            help="List only skipped test reasons.")
        state_p.add_argument('series', default='last', nargs='?',
                             help="The series to print status history for.")

    def _find_series(self, pav_cfg, series_name):
        """Grab the series based on the series name, if one was given."""

        if series_name == 'last':
            ser = cmd_utils.load_last_series(pav_cfg, self.errfile)
        else:
            try:
                ser = series.TestSeries.load(pav_cfg, series_name)
            except series.TestSeriesError as err:
                output.fprint(self.errfile,
                              "Could not load given series '{}'"
                              .format(series_name))
                output.fprint(self.errfile, err.pformat())
                return None

        return ser

    @sub_cmd()
    def _run_cmd(self, pav_cfg, args):
        """Gets called when `pav series <series_name>` is executed. """

        if args.skip_verify:
            series_cfg = series_config.load_series_config(pav_cfg, args.series_name)

            # Add the modes and overrides given by the user.
            series_cfg['modes'] += args.modes
            series_cfg['overrides'] += args.overrides

        else:
            # load series and test files
            try:
                # Pre-verify that all the series, tests, modes, and hosts exist.
                series_cfg = series_config.verify_configs(pav_cfg,
                                                          args.series_name,
                                                          host=args.host,
                                                          modes=args.modes,
                                                          overrides=args.overrides)
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

        output.fprint(self.outfile,
                      "Started series {sid}.\n"
                      "Run `pav series status {sid}` to view series status.\n"
                      "Run `pav series cancel {sid}` to cancel the series (and all its tests).\n"
                      "Run `pav series sets {sid}` to view status of individual test sets."
                      .format(sid=series_obj.sid))

        self.last_run_series = series_obj

        return 0

    @sub_cmd(*LIST_ALIASES)
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
            'errors',
            'passed',
            'failed',
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

    @sub_cmd(*SETS_ALIASES)
    def _sets_cmd(self, pav_cfg, args):
        """Display a series by test set."""

        ser = self._find_series(pav_cfg, args.series)
        if ser is None:
            return errno.EINVAL

        rows = []

        if args.merge_repeats:
            fields = ['name', 'iterations', 'complete', 'created', 'num_tests', 'scheduled',
                      'running', 'passed', 'failed', 'errors']
        else:
            fields = ['repeat', 'name', 'complete', 'created', 'num_tests', 'scheduled',
                      'running', 'passed', 'failed', 'errors']

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

        _ = self

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

    @sub_cmd(*STATE_ALIASES)
    def _state_history_cmd(self, pav_cfg: config.PavConfig, args):
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

        states = [status for status in ser.status.history()]
        if args.errors:
            # Filter out any non-errors.
            states = [state for state in states
                      if 'ERROR' in state.state]
        elif args.skipped:
            # Filter to just skipped messages
            states = [state for state in states
                      if state.state == 'TESTS_SKIPPED']

        if args.text:
            for status in states:
                output.fprint(self.outfile,
                              "{} {} {}".format(status.state, status.when, status.note))
            return 0
        else:
            output.draw_table(
                outfile=self.outfile,
                fields=['state', 'time', 'note'],
                rows=[state.as_dict() for state in states],
                field_info={
                    'time': {
                        'transform': output.get_relative_timestamp,
                        'title': 'When',
                    }
                }
            )

    @sub_cmd()
    def _cancel_cmd(self, pav_cfg, args):
        """Cancel all series found given the arguments."""

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
            ser.cancel(message="By user {}".format(utils.get_login()), cancel_tests=False)
            output.fprint(self.outfile, "Series {} cancelled.".format(ser.sid))

            tests_to_cancel.extend(ser.tests.values())

        output.fprint(self.outfile, "\nCancelling individual tests in each series.")

        return cancel_utils.cancel_tests(pav_cfg, tests_to_cancel,
                                         self.outfile, no_series_warning=True)
