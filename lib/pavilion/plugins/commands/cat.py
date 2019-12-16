import errno
import os
import sys

from pavilion import commands
from pavilion import utils

class FileCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'cat',
            'Print the contents of a pav <job id> file.',
            short_help="Print file information of <job id>"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'job_id', type=int,
            help="Job id number."
        )
        parser.add_argument(
            'file',
            type=str,
            help="name of a file within working_dir/tests/<job id>/"
        )

    def run(self, pav_cfg, args):

        test_dir = pav_cfg.working_dir/'test_runs'
        job_dir = utils.make_id_path(test_dir, args.job_id)

        if os.path.isdir(job_dir.as_posix()) is False:
            utils.fprint("directory '{}' does not exist."
                         .format(job_dir.as_posix()),
                         file=sys.stderr, color=utils.RED)
            return errno.EEXIST

        return print_file(job_dir/args.file)


def print_file(file):
    try:
        with open(file, 'r') as file:
            while True:
                block = file.read(4096)
                if not block:
                    break
                utils.fprint(block, file=sys.stdout)

    except IsADirectoryError:
        utils.fprint("{} is a directory.".format(file), sys.stderr,
                     color=utils.RED)
        return errno.EINVAL

    except FileNotFoundError:
        utils.fprint("file '{}' does not exist.".format(file), sys.stderr,
                     color=utils.RED)
        return errno.EEXIST
