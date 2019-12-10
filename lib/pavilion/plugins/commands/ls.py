import errno
import os
import re
import sys

from pavilion import commands
from pavilion import utils

class FileCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'ls',
            'List test artifact files of pav <job id>.',
            short_help="List pavilion <job id> files"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'job_id',
            help="Job id number."
        )

        parser.add_argument(
            'subdir',
            help="don't print color",
            nargs='?'
        )

    def run(self, pav_cfg, args):

        test_dir = pav_cfg.working_dir/'test_runs'
        job_dir = test_dir/args.job_id

        if os.path.isdir(job_dir.as_posix()) is False:
            err_dir(job_dir)

        if args.subdir:
            print_directory(job_dir/args.subdir)
        else:
            print_directory(job_dir)

        return 0

def print_directory(dir_):
    if os.path.isdir(dir_) is False:
        err_dir(dir_)

    for file in os.listdir(dir_):
        filename = os.path.join(dir_, file)
        if os.path.isdir(filename):
            utils.fprint(file, file=sys.stdout, color=utils.BLUE)
        elif os.path.islink(filename) is True:
            utils.fprint("{} -> {}".format(file, os.path.realpath(filename),
                                           file=sys.stdout))
        else:
            utils.fprint(file, file=sys.stdout)


def err_dir(dir_):
    utils.fprint("directory '{}' does not exist." .format(dir_),
                 file=sys.stderr, color=utils.RED)
    sys.exit()
