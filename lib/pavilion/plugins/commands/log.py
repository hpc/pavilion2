"""Print out the contents of the various log files for a given test run.
"""
import errno

from pavilion import commands
from pavilion import output
from pavilion import test_run


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

        subparsers.add_parser(
            'run',
            aliases=['run'],
            help="Displays log of run.",
            description="""Displays log of run."""
        )

        subparsers.add_parser(
            'kickoff',
            aliases=['kickoff'],
            help="Displays summary of kickoff.",
            description="""Displays summary of kickoff."""
        )

        subparsers.add_parser(
            'build',
            aliases=['build'],
            help="Displays summary of build.",
            description="""Displays summary of build."""
        )

        parser.add_argument('test', type=int,
                            help="Test number argument.")

    def run(self, pav_cfg, args):
        """Figure out which log the user wants and print it."""

        if args.log_cmd is None:
            self._parser.print_help(self.outfile)
            return errno.EINVAL
        else:
            cmd_name = args.log_cmd

        try:
            test = test_run.TestRun.load(pav_cfg, args.test)
        except test_run.TestRunError as err:
            output.fprint("Error loading test: {}".format(err),
                          color=output.RED,
                          file=self.errfile)
            return 1

        if 'run'.startswith(cmd_name):
            file_name = test.path / 'run.log'
        elif 'kickoff'.startswith(cmd_name):
            file_name = test.path / 'kickoff.log'
        elif 'build'.startswith(cmd_name):
            file_name = test.path / 'build' / 'pav_build_log'
        else:
            raise RuntimeError("Invalid log cmd '{}'".format(cmd_name))

        if not file_name.exists():
            output.fprint("Log file does not exist: {}"
                          .format(file_name),
                          color=output.RED,
                          file=self.errfile)
            return 1

        try:
            with file_name.open() as file:
                output.fprint(file.read(), file=self.outfile, width=None,
                              end="")
        except (IOError, OSError) as err:
            output.fprint("Could not read log file '{}': {}"
                          .format(file_name, err),
                          color=output.RED,
                          file=self.errfile)
            return 1

        return 0
