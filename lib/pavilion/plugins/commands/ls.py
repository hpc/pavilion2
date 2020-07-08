"""List the directory of the specified run."""

import errno
import os
import sys

from pavilion import commands
from pavilion import dir_db
from pavilion import output


class FileCommand(commands.Command):
    """List the directory (and maybe subdirs) of the given run."""

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
            type=str,
            metavar='DIR',
            nargs=1
        )

        parser.add_argument(
            '--tree',
            action='store_true',
            help="List JOB_ID file tree",
        )

    def run(self, pav_cfg, args):
        """List the run directory for the given run."""

        test_dir = pav_cfg.working_dir / 'test_runs'
        job_dir = dir_db.make_id_path(test_dir, args.job_id)

        if os.path.isdir(job_dir.as_posix()) is False:
            output.fprint("directory '{}' does not exist.".format(job_dir),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        if args.path is True:
            output.fprint(job_dir)
            return 0

        output.fprint(str(job_dir) + ':', file=self.outfile)

        if args.tree is True:
            level = 0
            self.tree_(level, job_dir)
            return 0

        if args.subdir:
            return self.ls_(job_dir / args.subdir[0])
        else:
            return self.ls_(job_dir)

    def ls_(self, dir_):
        """Print a directory listing for the given run directory."""

        if not dir_.is_dir():
            output.fprint("directory '{}' does not exist.".format(dir_),
                          file=self.errfile, color=output.RED)
            return errno.EEXIST

        for filename in dir_.iterdir():
            if filename.is_dir():
                output.fprint(filename.name, file=self.outfile,
                              color=output.BLUE)
            elif filename.is_symlink():
                output.fprint("{} -> {}".format(filename.name,
                                                filename.resolve()),
                              file=self.outfile,
                              color=output.CYAN)
            else:
                output.fprint(filename.name, file=self.outfile)

        return 0

    def tree_(self, level, path):
        """Print a full tree for the given path.
        :param int level: Indentation level.
        :param pathlib.Path path: Path to print the tree for.
        """
        for filename in path.iterdir():
            if filename.is_symlink():
                output.fprint("{}{} -> {}".format('    '*level,
                                                  filename.name,
                                                  filename.resolve()),
                              file=self.outfile,
                              color=output.CYAN)
            elif filename.is_dir():
                output.fprint("{}{}/".format('    '*level,
                                             filename.name),
                              file=self.outfile,
                              color=output.BLUE)
                self.tree_(level + 1, filename)
            else:
                output.fprint("{}{}".format('    '*level, filename.name),
                              file=self.outfile)
