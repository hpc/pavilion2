from pavilion import commands
from pavilion import schedulers
from pavilion import status_file
from pavilion import result_parsers
from pavilion import module_wrapper
from pavilion import system_variables
from pavilion import config
from pavilion import utils
from pavilion.test_config import DeferredVariable
from pavilion.test_config import find_all_tests
from pavilion.utils import fprint
import argparse
import errno
import sys
import yaml_config


class LogCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'log',
            'Diplays log.',
            short_help="Displays log for the given test id."
        )

    def _setup_arguments(self, parser):

        parser.add_argument('--test', help="Test number argument.", type=int)

        subparsers = parser.add_subparsers(
            dest="show_cmd",
            help="Types of information to show."
        )

        self._parser = parser

        run = subparsers.add_parser(
            'run',
            aliases=['run'],
            help="Displays log of run.",
            description="""Displays log of run."""
        )

        kickoff = subparsers.add_parser(
            'kickoff',
            aliases=['kickoff'],
            help="Displays summary of kickoff.",
            description="""Displays summary of kickoff."""
        )

        build = subparsers.add_parser(
            'build',
            aliases=['build'],
            help="Displays summary of build.",
            description="""Displays summary of build."""
        )

    def run(self, pav_cfg, args):

        if args.show_cmd is None:
            self._parser.print_help(self.outfile)
            return errno.EINVAL
        else:
            cmd_name = args.show_cmd

        if 'run'.startswith(cmd_name):
            file_name = str(pav_cfg.working_dir) + "/tests/" +str(args.test).zfill(7) + "/run.log"
        elif 'kickoff'.startswith(cmd_name):
            file_name = str(pav_cfg.working_dir) + "/tests/" + str(args.test).zfill(7)  + "/kickoff.log"
        elif 'build'.startswith(cmd_name):
            file_name = str(pav_cfg.working_dir) + "/tests/" + str(args.test).zfill(7) + "/build/pav_build_log"
        else:
            raise RuntimeError("Invalid show cmd '{}'".format(cmd_name))

        fprint("test # " + str(args.test).zfill(7))
        f_log = open(file_name, "r")
        fprint(f_log.read())

        return 0

