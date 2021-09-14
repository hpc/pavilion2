"""Prints files from a given test run id."""

import errno
import os
import sys

from pavilion import commands
from pavilion import dir_db
from pavilion import output


class FileCommand(commands.Command):
    """Prints the given file for a given test run id."""

    def __init__(self):
        super().__init__(
            'cat',
            'Print the contents of a pav <job id> file.',
            short_help="Print file information of <job id>"
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            'job_id', type=int,
            help="job id",
            metavar='JOB_ID'
        )
        parser.add_argument(
            'file',
            help="filename",
            metavar='FILE',
            type=str,
        )

    def run(self, pav_cfg, args):
        """Run this command."""

        test_dir = pav_cfg.working_dir / 'test_runs'
        job_dir = dir_db.make_id_path(test_dir, args.job_id)

        if os.path.isdir(job_dir.as_posix()) is False:
            output.fprint("directory '{}' does not exist."
                          .format(job_dir.as_posix()),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        return self.print_file(job_dir / args.file)

    def print_file(self, file):
        """Print the file at the given path.
        :param path file: The path to the file to print.
        """

        try:
            with file.open() as file:
                while True:
                    block = file.read(4096)
                    if not block:
                        break
                    output.fprint(block, width=None, file=self.outfile, end="")

        except FileNotFoundError:
            output.fprint("file '{}' does not exist.".format(file),
                          file=sys.stderr, color=output.RED)
            return errno.EEXIST

        except IsADirectoryError:
            output.fprint("{} is a directory.".format(file),
                          file=sys.stderr, color=output.RED)
            return errno.EINVAL

        except (IOError, OSError, PermissionError) as err:
            output.fprint("Error opening file '{}': {}".format(file, err),
                          color=output.RED)
            return errno.EIO
