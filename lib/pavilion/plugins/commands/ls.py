import errno
import os
import sys

from pavilion import commands
from pavilion import output
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
            'job_id', type=int,
            help="Job id number."
        )

        parser.add_argument(
            'subdir',
            help="Subdirectory to print.",
            nargs='?'
        )

    def run(self, pav_cfg, args):

        test_dir = pav_cfg.working_dir / 'test_runs'
        job_dir = utils.make_id_path(test_dir, args.job_id)

        if os.path.isdir(job_dir.as_posix()) is False:
            output.fprint("directory '{}' does not exist.".format(job_dir),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        if args.subdir:
            return print_directory(job_dir / args.subdir)
        else:
            return print_directory(job_dir)


def print_directory(dir_):
    if os.path.isdir(dir_) is False:
        output.fprint("directory '{}' does not exist.".format(dir_),
                      file=sys.stderr, color=output.RED)
        return errno.EEXIST

    for file in os.listdir(dir_):
        filename = os.path.join(dir_, file)
        if os.path.isdir(filename):
            output.fprint(file, file=sys.stdout, color=output.BLUE)
        elif os.path.islink(filename) is True:
            output.fprint("{} -> {}".format(file, os.path.realpath(filename),
                                            file=sys.stdout))
        else:
            output.fprint(file, file=sys.stdout)

    return 0
