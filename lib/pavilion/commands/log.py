"""Print out the contents of the various log files for a given test run.
"""

import datetime
import errno
import time
import sys

from pavilion import errors
from pavilion import output
from pavilion import series, series_config
from pavilion.test_run import TestRun
from .base_classes import Command


class LogCommand(Command):
    """Print the contents of log files for test runs."""

    follow_testing = False
    sleep_timeout = 1

    def __init__(self):
        super().__init__(
            'log',
            'Displays log.',
            short_help="Displays log for the given test id."
        )

        self._parser = None

    def _setup_arguments(self, parser):

        subparsers = parser.add_subparsers(
            dest="log_cmd",
            help="Types of information to show."
        )

        self._parser = parser

        run = subparsers.add_parser(
            'run',
            help="Show a test's run.log",
            description="Displays the test run log (run.log)."
        )
        run.add_argument('id', type=str,
                         help="Test number or series id (e.g. s7) argument.")

        kickoff = subparsers.add_parser(
            'kickoff',
            help="Show a test's kickoff.log",
            description="Displays the kickoff log (kickoff.log)"
        )
        kickoff.add_argument('id', type=str,
                             help="Test number or series id (e.g. s7) "
                                  "argument.")

        build = subparsers.add_parser(
            'build',
            help="Show a test's build.log",
            description="Displays the build log (build.log)"
        )
        build.add_argument('id', type=str,
                           help="Test number or series id (e.g. s7) argument.")

        results = subparsers.add_parser(
            'results',
            help="Show a test's results.log",
            description="Displays the results log (results.log)"
        )
        results.add_argument('id', type=str,
                             help="Test number or series id (e.g. s7) "
                                  "argument.")

        series_cmd = subparsers.add_parser(
            'series',
            help="Show a series's output (series.out).",
            description="Displays the series output (series.log)."
        )
        series_cmd.add_argument('id', type=str,
                                help="Test number or series id (e.g. s7) argument.")

        subparsers.add_parser(
            'global',
            help="Show Pavilion's global output log.",
            description="Displays Pavilion's global output log."
        )

        states_cmd = subparsers.add_parser(
            'states',
            help="Show a tests's state history.",
            description="Displays the state ('<test_id>/status' file in full for a given test.")
        states_cmd.add_argument(
            '--raw', action='store_true', help="Print the state file as is.")
        states_cmd.add_argument(
            '--raw_time', action='store_true', help="Print raw unix timestamps.")
        states_cmd.add_argument('id', help="The test id to show states for.")

        subparsers.add_parser(
            'all_results',
            aliases=['allresults', 'all-results'],
            help="Show Pavilion's general result log.",
            description="Displays general Pavilion result log."
        )

        parser.add_argument(
            '--tail', '-n', default=None, required=False, type=int,
            help="Output the last N lines."
        )

        parser.add_argument(
            '--follow', '-f', action='store_true',
            help="Prints the log to the terminal as its being written."
        )

    LOG_PATHS = {
        'build': 'build.log',
        'kickoff': 'job/kickoff.log',
        'results': 'results.log',
        'run': 'run.log',
        'series': 'series.out'
    }

    def error_msg(self, err_msg: str, follow: bool):
        """Prints the error message."""

        output.fprint(self.errfile, err_msg, color=output.RED, end='')

        # If we are following, add 'Checking again...' message to error message, and then sleep.
        if follow:
            output.fprint(self.errfile, ". Checking again...", color=output.RED, end='\r')
            time.sleep(self.sleep_timeout)
            output.clear_line(self.errfile)
        else:
            # This fprint is purely for visual satisfaction.
            output.fprint(self.errfile)
            return 1

    def run(self, pav_cfg, args):
        """Figure out which log the user wants and print it."""

        if args.log_cmd is None:
            self._parser.print_help(self.outfile)
            return errno.EINVAL
        else:
            cmd_name = args.log_cmd

        if cmd_name == 'states':
            return self._states(pav_cfg, args.id, raw=args.raw, raw_time=args.raw_time)

        if cmd_name in ['global', 'all_results', 'allresults', 'all-results']:
            if 'results' in cmd_name:
                file_name = pav_cfg.working_dir/'results.log'
            else:
                file_name = pav_cfg.working_dir/'pav.log'

        else:
            try:
                if cmd_name == 'series':
                    test = series.TestSeries.load(pav_cfg, args.id)
                else:
                    test = TestRun.load_from_raw_id(pav_cfg, args.id)
            except errors.TestRunError as err:
                output.fprint(self.errfile, "Error loading test.", err, color=output.RED)
                return 1
            except series_config.SeriesConfigError as err:
                output.fprint(self.errfile, "Error loading series.", err, color=output.RED)
                return 1

            file_name = test.path/self.LOG_PATHS[cmd_name]

        # For build log, there are 4 different paths to check. This adds all the other paths
        # for the build log to the file_paths to check
        file_paths = [file_name]
        if cmd_name == 'build':
            file_paths.append(test.path/'build/pav_build_log')
            file_paths.append(test.builder.log_path)
            file_paths.append(test.builder.tmp_log_path)

        first_loop = True
        current_position = 0
        while args.follow or first_loop:
            if any(_file_path.exists() for _file_path in file_paths):
                for file_path in file_paths:
                    if file_path.exists():
                        try:
                            with file_path.open() as file:
                                if first_loop:
                                    if args.tail:
                                        tail = file.readlines()[-int(args.tail):]
                                        for line in tail:
                                            output.fprint(self.outfile, line, flush=True)
                                        current_position = file.tell()
                                    else:
                                        output.fprint(self.outfile, file.read(), width=None, end='')

                                if args.follow:
                                    file.seek(current_position)
                                    data = file.read()
                                    end_position = file.tell()
                                    if end_position > current_position:
                                        current_position = end_position
                                        output.fprint(self.outfile, data, flush=True)
                                    else:
                                        time.sleep(self.sleep_timeout)

                        except (IOError, OSError) as err:
                            # There is a possibility that the log file was moved mid-execution so if
                            # we are following, we will check again.
                            self.error_msg("Could not read log file '{}'".format(file_path),
                                        args.follow)
                        break
            else:
                self.error_msg("Log file does not exist: {}".format(file_paths[0]), args.follow)

            first_loop = False

            # For unit tests to stop the follow feature
            if self.follow_testing:
                break
        return 0

    def _states(self, pav_cfg, test_id, raw=False, raw_time=False):
        """Print the states for a test."""

        try:
            test = TestRun.load_from_raw_id(pav_cfg, test_id)
        except errors.TestRunError as err:
            output.fprint(self.errfile, "Error loading test.", err, color=output.RED)
            return 1

        states = test.status.history()

        states = [state.as_dict() for state in states]

        if not raw_time:
            for state in states:
                state['time'] = datetime.datetime.fromtimestamp(state['time']).isoformat(' ')

        if raw:
            for state in states:
                output.fprint(self.outfile,
                             "{time} {state} {note}".format(**state))
        else:
            output.draw_table(
                self.outfile,
                rows=states,
                fields=['time', 'state', 'note'],)

        return 0
