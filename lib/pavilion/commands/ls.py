"""List the directory of the specified run."""

import errno
import os
import sys

from pavilion import dir_db
from pavilion import output
from .base_classes import Command


class LSCommand(Command):
    """List the directory (and maybe subdirs) of the given run."""

    def __init__(self):
        super().__init__(
            'ls',
            'List test artifact files of pav <job id>.',
            short_help="List pavilion <job id> files"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'test_id', type=int,
            help="Test id number.",
            metavar='TEST_ID',
        )
        parser.add_argument(
            '--path',
            action='store_true',
            help='print test absolute path',
        )
        parser.add_argument(
            'subdir',
            metavar='DIR',
            nargs='?',
            help="print subdirectory DIR.",
        )

        parser.add_argument(
            '--tree',
            action='store_true',
            help="List file tree for the given test run.",
        )

    def run(self, pav_cfg, args):
        """List the run directory for the given run."""

        test_run_dir = pav_cfg.working_dir / 'test_runs'
        test_dir = dir_db.make_id_path(test_run_dir, args.test_id)
        if args.subdir:
            test_dir = test_dir/args.subdir

        if os.path.isdir(test_dir.as_posix()) is False:
            output.fprint("directory '{}' does not exist.".format(test_dir),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        if args.path is True:
            output.fprint(test_dir)
            return 0

        output.fprint(str(test_dir) + ':', file=self.outfile)

        if args.tree is True:
            level = 0
            self.tree_(level, test_dir)
            return 0

        return self.ls_(test_dir)

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
