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
            help="Job id number.",
            metavar='JOB_ID',
        )
        parser.add_argument(
            '--path',
            action='store_true',
            help='print job_id absolute path',
        )
        parser.add_argument(
            '--subdir',
            help="print subdirectory DIR.",
            metavar = 'DIR',
            nargs=1
        )

        parser.add_argument(
            '--tree',
            action='store_true',
            help="List JOB_ID file tree",
        )

    def run(self, pav_cfg, args):

        test_dir = pav_cfg.working_dir / 'test_runs'
        job_dir = utils.make_id_path(test_dir, args.job_id)

        if os.path.isdir(job_dir.as_posix()) is False:
            output.fprint("directory '{}' does not exist.".format(job_dir),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        if args.path is True:
            output.fprint(job_dir)
            return 0

        output.fprint(str(job_dir) + ':', file=sys.stdout)

        if args.tree is True:
            level = 0
            tree_(level, job_dir)
            return 0

        if args.subdir:
            return ls_(job_dir / args.subdir)
        else:
            return ls_(job_dir)

def ls_(dir_):
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

def tree_(level, path):
    for file in os.listdir(path):
        filename = os.path.join(path, file)
        if os.path.islink(filename):
            output.fprint("{}{} -> {}".format(' '*4*level, file,
                                             os.path.realpath(filename)),
                         file=sys.stdout, color=output.CYAN)
        elif os.path.isdir(filename):
            output.fprint("{}{}/".format(' '*4*level, file),
                         file=sys.stdout, color=output.BLUE)
            tree_(level + 1, filename)
        else:
            output.fprint("{}{}".format(' '*4*level, file), file=sys.stdout)
