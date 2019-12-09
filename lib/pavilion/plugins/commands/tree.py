import errno
import os
import re
import sys

from pavilion import commands
from pavilion import utils

class FileCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'tree',
            'List test artifact files of pav <job id>.',
            short_help="List pavilion <job id> files"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'job_id',
            help="Job id number."
        )

    def run(self, pav_cfg, args):

        test_dir = pav_cfg.working_dir/'test_runs'
        job_dir = test_dir/args.job_id

        if os.path.isdir(job_dir.as_posix()) is False:
            utils.fprint("directory '{}' does not exist."
                         .format(job_dir.as_posix()),
                         file=sys.stderr, color=utils.RED)
            sys.exit()

        level = 0
        print_directory(level, job_dir)
        return 0

def print_directory(level, path):
    for file in os.listdir(path):
        if os.path.isdir(os.path.join(path, file)):
            utils.fprint("{}{}/".format(' '*4*level, str(file)),
                         file=sys.stdout, color=utils.BLUE)
            print_directory(level + 1, os.path.join(path, file))
        else:
            utils.fprint("{}{}".format(' '*4*level, file), file=sys.stdout)
