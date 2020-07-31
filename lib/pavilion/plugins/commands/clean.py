"""Clean old tests/builds/etc from the working directory."""

import errno
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from pavilion import builder
from pavilion import commands
from pavilion import clean
from pavilion import output
from pavilion import dir_db
from pavilion.status_file import STATES
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


class CleanCommand(commands.Command):
    """Cleans outdated test and series run directories."""

    def __init__(self):
        super().__init__(
            'clean',
            'Clean up Pavilion working directory. Remove tests and downloads '
            'older than the cutoff date (default 30 days). Remove series and'
            'builds that don\'t correspond to any test runs (possibly because'
            'you just deleted those old runs).',
            short_help="Clean up Pavilion working directory."
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true', default=False,
            help='Verbose output.'
        )

        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '--older-than', action='store',
            help='Set the max age of files to be removed. Can be a date ex:'
                 '"Jan 1 2019" or , or a number of days/weeks ex:"32 weeks"'
        )
        group.add_argument(
            '-a', '--all', action='store_true',
            help='Attempts to remove everything in the working directory, '
                 'regardless of age.'
        )

    def run(self, pav_cfg, args):
        """Run this command."""

        try:
            cutoff_date = self.validate_args(args)
        except OlderThanError as err:
            output.fprint("Command Argument Error: \n{}"
                          .format(err),
                          color=output.RED, file=self.errfile)
            return errno.EINVAL
        except InvalidDateError as err:
            output.fprint("Command Argument Error: \n{}"
                          .format(err),
                          color=output.RED, file=self.errfile)
            return errno.EINVAL

        end = '\n' if args.verbose else '\r'

        # Clean Tests
        tests_dir = pav_cfg.working_dir / 'test_runs'     # type: Path
        output.fprint("Removing Tests...", file=self.outfile, end=end)
        removed_tests = clean.delete_tests_by_date(pav_cfg, tests_dir,
                                                   cutoff_date,
                                                   args.verbose)
        output.fprint("Removed {} test(s).".format(removed_tests),
                      file=self.outfile, color=output.GREEN, clear=True)

        # Clean Series
        series_dir = pav_cfg.working_dir / 'series'       # type: Path
        output.fprint("Removing Series...", file=self.outfile, end=end)
        removed_series = clean.delete_series(series_dir, args.verbose)
        output.fprint("Removed {} series.".format(removed_series),
                      file=self.outfile, color=output.GREEN, clear=True)

        # Clean Builds
        builds_dir = pav_cfg.working_dir / 'builds'        # type: Path
        output.fprint("Removing Builds...", file=self.outfile, end=end)
        removed_builds = builder.delete_unused(tests_dir, builds_dir,
                                               args.verbose)
        builder.remove_lingering_finished_files(builds_dir)
        output.fprint("Removed {} build(s).".format(removed_builds),
                      file=self.outfile, color=output.GREEN, clear=True)

        return 0

    def validate_args(self, args):
        """Validate the command arguments. Basically, ensure that the
        provided cutoff date is a valid date.

        :param args: The parsed command line argument object.

        """

        cutoff_date = datetime.today() - timedelta(days=30)

        if args.older_than:
            args.older_than = args.older_than.split()

            if len(args.older_than) == 2:

                if not args.older_than[0].isdigit():
                    raise OlderThanError(
                        "Invalid `--older-than` value."
                    )

                if args.older_than[1] in ['minute', 'minutes']:
                    cutoff_date = datetime.today() - timedelta(
                        minutes=int(args.older_than[0]))
                elif args.older_than[1] in ['hour', 'hours']:
                    cutoff_date = datetime.today() - timedelta(
                        hours=int(args.older_than[0]))
                elif args.older_than[1] in ['day', 'days']:
                    cutoff_date = datetime.today() - timedelta(
                        days=int(args.older_than[0]))
                elif args.older_than[1] in ['week', 'weeks']:
                    cutoff_date = datetime.today() - timedelta(
                        weeks=int(args.older_than[0]))
                elif args.older_than[1] in ['month', 'months']:
                    cutoff_date = datetime.today() - timedelta(
                        days=30*int(args.older_than[0]))
                else:
                    raise OlderThanError(
                        "Invalid --older-than value: {}"
                        .format(args.older_than[1])
                    )

            elif len(args.older_than) == 3:
                date = ' '.join(args.older_than)
                try:
                    cutoff_date = datetime.strptime(date, '%b %d %Y')
                except ValueError as err:
                    raise InvalidDateError("{} is not a valid date: {}".format(date,
                                                                        err))
            else:
                raise OlderThanError(
                    "Invalid `--older-than` value."
                )

        elif args.all:
            cutoff_date = datetime.today()

        return cutoff_date

class OlderThanError(RuntimeError):
    """Error to raise for invalid older than argument."""

class InvalidDateError(RuntimeError):
    """Error to raise for invalid date arguments."""

