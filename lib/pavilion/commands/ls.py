"""List the directory of the specified run."""
import collections
import errno
import grp
import pwd
import os
import shutil
import sys
import stat

from pavilion import dir_db
from pavilion import output
from pavilion import utils
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
            help='print just the test run absolute path',
        )
        parser.add_argument(
            '--perms', '-p',
            action='store_true',
            help='Show file permissions and ownership.'
        )
        parser.add_argument(
            '--size', '-s',
            action='store_true',
            help='Show file size (human readable),'
        )
        parser.add_argument(
            '--date', '-d',
            action='store_true',
            help='Show a timestamp for each file.'
        )
        parser.add_argument(
            '--symlink', '-r',
            action='store_true',
            help='Show symlink destinations.',
        )
        parser.add_argument(
            '--long', '-l',
            action='store_true',
            help='Show long output (as if -psrd were given).'
        )
        parser.add_argument(
            '--tree',
            action='store_true',
            help="List file tree for the given test run (may be huge). Most output args don't"
                 "apply.",
        )
        parser.add_argument(
            'subdir',
            metavar='DIR',
            nargs='?',
            help="print subdirectory DIR.",
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

        symlink = args.symlink or args.long
        perms = args.perms or args.long
        size = args.size or args.long
        date = args.date or args.long

        return self.ls_(test_dir, symlink, perms, size, date)

    BASE_FN_WIDTH = 40

    def ls_(self, dir_, show_symlinks, show_perms, show_size, show_date):
        """Print a directory listing for the given run directory."""

        if not dir_.is_dir():
            output.fprint("directory '{}' does not exist.".format(dir_),
                          file=self.errfile, color=output.RED)
            return errno.EEXIST

        files = []
        for file in dir_.iterdir():
            filename = file.name
            file_info = {'target': ''}

            if file.is_symlink():
                if not file.exists():
                    filename = output.ANSIString(filename, code=output.RED)
                elif show_symlinks:
                    resolved = file.resolve()
                    abs_path = file.absolute()
                    rel = utils.relative_to(resolved, abs_path.parent)
                    rel_str = str(rel)
                    res_str = str(resolved)
                    dest = rel_str if len(res_str) > len(rel_str) else res_str
                    filename = output.ANSIString(filename, code=output.CYAN)
                    file_info['target'] = output.ANSIString(dest, code=output.CYAN)
                else:
                    if file.is_dir():
                        filename += '/'
                    filename = output.ANSIString(filename, code=output.CYAN)
            elif file.is_dir():
                filename += '/'
                filename = output.ANSIString(filename, code=output.BLUE)

            file_info['filename'] = filename

            if show_perms or show_size or show_date:
                if file.exists():
                    fstat = file.stat()
                    file_info['group'] = file.group()
                    file_info['owner'] = file.owner()
                else:
                    fstat = file.lstat()
                    try:
                        file_info['group'] = grp.getgrgid(fstat.st_gid).gr_name
                    except KeyError:
                        file_info['group'] = fstat.st_gid
                    try:
                        file_info['owner'] = pwd.getpwuid(fstat.st_uid).pw_name
                    except KeyError:
                        file_info['owner'] = fstat.st_uid

                file_info['perms'] = stat.filemode(fstat.st_mode)
                file_info['size'] = utils.human_readable_size(fstat.st_size)
                file_info['date'] = output.get_relative_timestamp(fstat.st_mtime)

            files.append(file_info)

        max_widths = collections.defaultdict(lambda: 0)
        for file_info in files:
            for key in file_info:
                max_widths[key] = max(max_widths[key], len(file_info[key]))

        line_format = ['{{filename:{}s}}  '.format(max_widths['filename'])]

        if show_perms:
            line_format.append('{{owner:{}s}}'.format(max_widths['owner']))
            line_format.append('{{group:{}s}}'.format(max_widths['group']))
            line_format.append('{{perms:{}s}}'.format(max_widths['perms']))

        if show_size:
            line_format.append('{{size:{}s}}'.format(max_widths['size']))

        if show_date:
            line_format.append('{{date:{}s}}'.format(max_widths['date']))

        if show_symlinks:
            line_format.append('{target}')

        line_format = ' '.join(line_format)

        for file_info in files:
            line = line_format.format(**file_info)
            output.fprint(line, file=self.outfile)

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
