"""Clean old tests/builds/etc from the working directory."""

import errno
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from pavilion import commands
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
            '--all', '-a', action='store_true',
            help='Attempts to remove everything in the working directory, '
                 'regardless of age.'
        )

    def run(self, pav_cfg, args):
        """Run this command."""

        cutoff_date = datetime.today() - timedelta(days=30)

        if args.older_than:
            args.older_than = args.older_than.split()

            if len(args.older_than) == 2:

                if not args.older_than[0].isdigit():
                    raise commands.CommandError(
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
            elif len(args.older_than) == 3:
                date = ' '.join(args.older_than)
                try:
                    cutoff_date = datetime.strptime(date, '%b %d %Y')
                except (TypeError, ValueError):
                    output.fprint("{} is not a valid date."
                                  .format(args.older_than),
                                  file=self.errfile, color=output.RED)
                    return errno.EINVAL
            else:
                output.fprint(
                    "Invalid `--older-than` value.", file=self.errfile,
                    color=output.RED
                )
                return errno.EINVAL
        elif args.all:
            cutoff_date = datetime.today()

        tests_dir = pav_cfg.working_dir / 'test_runs'     # type: Path
        series_dir = pav_cfg.working_dir / 'series'       # type: Path
        build_dir = pav_cfg.working_dir / 'builds'        # type: Path

        removed_tests = 0
        removed_series = 0
        removed_builds = 0

        used_builds = set()

        # Clean Tests
        output.fprint("Removing Tests...", file=self.outfile,
                      color=output.GREEN)
        dir_db.delete(tests_dir, pav_cfg, cutoff_date)

        # Clean Series
        output.fprint("Removing Series...", file=self.outfile,
                      color=output.GREEN)
        dir_db.delete(series_dir)

        # Clean Builds
        output.fprint("Removing Builds...", file=self.outfile,
                      color=output.GREEN)
        for build in build_dir.iterdir():
            if build in used_builds:
                continue

            try:
                shutil.rmtree(build.as_posix())
                if args.verbose:
                    output.fprint("Removed build", build, file=self.outfile)
            except OSError as err:
                output.fprint(
                    "Could not remove build {}: {}"
                    .format(build, err),
                    color=output.YELLOW, file=self.errfile)

        output.fprint("Removed {tests} tests, {series} series, and {builds} "
                      "builds."
                      .format(tests=removed_tests, series=removed_series,
                              builds=removed_builds),
                      color=output.GREEN, file=self.outfile)
        return 0
    """
