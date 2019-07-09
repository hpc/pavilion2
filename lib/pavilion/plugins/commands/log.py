import errno
import sys

from pavilion import commands
from pavilion import utils
from pavilion import pav_test


class LogCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'log',
            'Diplays log.',
            short_help="Displays log for the given test id."
        )

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

    def run(self, pav_cfg, args, out_file=sys.stdout, err_file=sys.stderr):

        if args.log_cmd is None:
            self._parser.print_help(self.outfile)
            return errno.EINVAL
        else:
            cmd_name = args.log_cmd

        try:
            test = pav_test.PavTest.load(pav_cfg, args.test)
        except pav_test.PavTestError as err:
            utils.fprint("Error loading test: {}".format(err),
                         color=utils.RED,
                         file=err_file)
            return 1

        if 'run'.startswith(cmd_name):
            file_name = test.path/'run.log'
        elif 'kickoff'.startswith(cmd_name):
            file_name = test.path/'kickoff.log'
        elif 'build'.startswith(cmd_name):
            file_name = test.path/'build'/'pav_build_log'
        else:
            raise RuntimeError("Invalid log cmd '{}'".format(cmd_name))

        if not file_name.exists():
            utils.fprint("Log file does not exist: {}"
                         .format(file_name),
                         color=utils.RED,
                         file=err_file)
            return 1

        try:
            with file_name.open() as file:
                utils.fprint(file.read(), file=out_file)
        except (IOError, OSError) as err:
            utils.fprint("Could not read log file '{}': {}"
                         .format(file_name, err),
                         color=utils.RED,
                         file=out_file)
            return 1

        return 0
