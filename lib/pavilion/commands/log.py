"""Print out the contents of the various log files for a given test run.
"""
import errno
import time

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

    def run(self, pav_cfg, args):
        """Figure out which log the user wants and print it."""

        if args.log_cmd is None:
            self._parser.print_help(self.outfile)
            return errno.EINVAL
        else:
            cmd_name = args.log_cmd

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
            file_paths = [file_name]
            if cmd_name == 'build':
                file_paths.append(test.builder.log_path)
                file_paths.append(test.builder.tmp_log_path)

        first_loop = True
        current_position = 0
        while args.follow or first_loop:
            first_loop = False
            for file_path in file_paths:
                if file_path.exists():
                    try:
                        with file_path.open() as file:
                            if args.tail:
                                tail = file.readlines()[-int(args.tail):]
                                for line in tail:
                                    output.fprint(self.outfile, line)
                            elif args.follow:
                                file.seek(current_position)
                                data = file.read()
                                end_position = file.tell()
                                if end_position > current_position:
                                    current_position = end_position
                                    output.fprint(self.outfile, data, flush=True, end='')
                                time.sleep(self.sleep_timeout)
                            else:
                                output.fprint(self.outfile, file.read(), width=None, end='\n')

                    except (IOError, OSError) as err:
                        output.fprint(self.errfile, "Could not read log file '{}'"
                                    .format(file_path), err, color=output.RED, end='')
                        if args.follow:
                            output.fprint(self.errfile, "... Checking again", err,
                                        color=output.RED, end='\r')
                            output.clear_line(self.errfile)
                        else:
                            return 1
                    break
                else:
                    output.fprint(self.errfile, "Log file does not exist: {}"
                            .format(file_path), color=output.RED, end='')
                    if args.follow:
                        output.fprint(self.errfile, "... Checking again", color=output.RED, end='\r')
                        time.sleep(self.sleep_timeout)
                        output.clear_line(self.errfile)

        return 0
