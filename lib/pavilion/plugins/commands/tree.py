import errno
import os
import sys

from pavilion import commands
from pavilion import output
from pavilion import utils


class FileCommand(commands.Command):

    def __init__(self):
        super().__init__(
            'tree',
            'Print pav <job id> test directory file tree.',
            short_help="List <job id> file tree"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'job_id', type=int,
            help="Job id number."
        )

    def run(self, pav_cfg, args):
        test_dir = pav_cfg.working_dir / 'test_runs'
        job_dir = utils.make_id_path(test_dir, args.job_id)

        if os.path.isdir(job_dir.as_posix()) is False:
            output.fprint("directory '{}' does not exist."
                          .format(job_dir.as_posix()),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        level = 0
        print_directory(level, job_dir)
        return 0


def print_directory(level, path):
    for file in os.listdir(path):
        filename = os.path.join(path, file)
        if os.path.islink(filename):
            output.fprint("{}{} -> {}".format(' ' * 4 * level, file,
                                              os.path.realpath(filename)),
                          file=sys.stdout, color=output.CYAN)
        elif os.path.isdir(filename):
            output.fprint("{}{}/".format(' ' * 4 * level, file),
                          file=sys.stdout, color=output.BLUE)
            print_directory(level + 1, filename)
        else:
            output.fprint("{}{}".format(' ' * 4 * level, file), file=sys.stdout)
