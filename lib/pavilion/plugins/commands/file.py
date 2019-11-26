import errno
import os
import sys

from pavilion import commands
from pavilion import utils

class FileCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'file',
            'List files and file contents associated with pav <job id>.',
            short_help="List file information of <job id>"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'job_id',
            help="Job id number."
        )
        parser.add_argument(
            '--filename',
            type=str,
            help="name of a file within working_dir/tests/<job id>/"
        )

    def run(self, pav_cfg, args, out_file=sys.stdout, err_file=sys.stderr):

        test_dir = pav_cfg.working_dir/'tests'
        job_dir = test_dir/args.job_id

        if os.path.isdir(job_dir.as_posix()) is True:
            if args.filename is not None:
                print_file(job_dir/args.filename)
            else:
                for file_ in os.listdir(job_dir):
                    utils.fprint(file_, file=out_file)
        else:
            utils.fprint("file '{}' does not exist.".format(job_dir.as_posix()),
                         file=err_file)
            sys.exit()
        return 0


def print_file(filename, out_file=sys.stdout, err_file=sys.stderr):
    try:
        with open(filename, 'r') as file_:
            while True:
                block = file_.read(4096)
                if not block:
                    break
                utils.fprint(block, file=out_file)

    except IsADirectoryError:
        utils.fprint("{} is a directory.".format(filename), err_file)
        sys.exit()

    except FileNotFoundError:
        utils.fprint("file '{}' does not exist.".format(filename), err_file)
        sys.exit()
