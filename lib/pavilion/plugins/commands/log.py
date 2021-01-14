"""Print out the contents of the various log files for a given test run.
"""
import errno
import subprocess

from pavilion import commands
from pavilion import output
from pavilion import test_run
from pavilion import series, series_config


class LogCommand(commands.Command):
    """Print the contents of log files for test runs."""

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
        run.add_argument('ts_id', type=str,
                         help="Test number or series id (e.g. s7) argument.")

        kickoff = subparsers.add_parser(
            'kickoff',
            help="Show a test's kickoff.log",
            description="Displays the kickoff log (kickoff.log)"
        )
        kickoff.add_argument('ts_id', type=str,
                             help="Test number or series id (e.g. s7) "
                                  "argument.")

        build = subparsers.add_parser(
            'build',
            help="Show a test's build.log",
            description="Displays the build log (build.log)"
        )
        build.add_argument('ts_id', type=str,
                           help="Test number or series id (e.g. s7) argument.")

        results = subparsers.add_parser(
            'results',
            help="Show a test's results.log",
            description="Displays the results log (results.log)"
        )
        results.add_argument('ts_id', type=str,
                             help="Test number or series id (e.g. s7) "
                                  "argument.")

        series = subparsers.add_parser(
            'series',
            help="Show a series's output (series.out).",
            description="Displays the series output (series.log)."
        )
        series.add_argument('ts_id', type=str,
                            help="Test number or series id (e.g. s7) argument.")

        general = subparsers.add_parser(
            'general_log',
            help="Show Pavilion's general output log.",
            description="Displays general Pavilion output log."
        )
        general.add_argument(
            '--lines', '-n', default=10, required=False,
            help="Output the last N lines, default is last 10."
        )

        general = subparsers.add_parser(
            'general_result',
            help="Show Pavilion's general result log.",
            description="Displays general Pavilion result log."
        )
        general.add_argument(
            '--lines', '-n', default=10, required=False,
            help="Output the last N lines, default is last 10."
        )

    LOG_PATHS = {
        'build': 'build.log',
        'kickoff': 'kickoff.log',
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

        if cmd_name in ['general_log', 'general_result']:
            if 'result' in cmd_name:
                file_name = pav_cfg.working_dir/'results.log'

            else:
                file_name = pav_cfg.working_dir/'pav.log'

        else:
            try:
                if cmd_name == 'series':
                    test = series.TestSeries.from_id(pav_cfg, args.ts_id)
                else:
                    test = test_run.TestRun.load(pav_cfg, int(args.ts_id))
            except test_run.TestRunError as err:
                output.fprint("Error loading test: {}".format(err),
                              color=output.RED,
                              file=self.errfile)
                return 1
            except series_config.SeriesConfigError as err:
                output.fprint("Error loading series: {}".format(err),
                              color=output.RED,
                              file=self.errfile)
                return 1

            file_name = test.path/self.LOG_PATHS[cmd_name]

        if not file_name.exists():
            output.fprint("Log file does not exist: {}"
                          .format(file_name),
                          color=output.RED,
                          file=self.errfile)
            return 1

        try:
            # "Tail" general log files.
            if cmd_name in ['general_log', 'general_result']:
                with file_name.open() as file:
                    tail = file.readlines()[-int(args.lines):]
                    for line in tail:
                        output.fprint(line, file=self.outfile)

            # Print full files for specific IDs.
            else:
                with file_name.open() as file:
                    output.fprint(file.read(), file=self.outfile, width=None,
                                  end='')

        except (IOError, OSError) as err:
            output.fprint("Could not read log file '{}': {}"
                          .format(file_name, err),
                          color=output.RED,
                          file=self.errfile)
            return 1

        return 0
