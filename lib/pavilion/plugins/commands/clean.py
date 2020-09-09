"""Clean old tests/builds/etc from the working directory."""

import argparse
import errno
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from pavilion import builder
from pavilion import commands
from pavilion import clean
from pavilion import dir_db
from pavilion import filters
from pavilion import output
from pavilion import utils
from pavilion.status_file import STATES
from pavilion.test_run import TestRun, TestRunError, TestRunNotFoundError


class CleanCommand(commands.Command):
    """Cleans outdated test and series run directories."""

    def __init__(self):
        super().__init__(
            'clean',
            "Clean up Pavilion working directory. Removes tests either all or "
            "those older than the corresponding '--older-than' flag. Removes "
            "series and builds that don\'t correspond to any test runs "
            "(possibly because you just deleted those old runs).",
            short_help="Clean up Pavilion working directory."
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true', default=False,
            help='Verbose output.'
        ),
        group = parser.add_mutually_exclusive_group()
        group.add_argument(
            '-a', '--all', action='store_true',
            help='Attempts to remove everything in the working directory, '
                 'regardless of age.'
        ),
        group.add_argument(
            '--older-than', type=utils.hr_cutoff_to_datetime, default='30days',
            help=("Remove only tests/series older than (by creation "
                  "time) the given date or a time period given relative to "
                  "the current date. \n\nThis can be in the format a partial "
                  "ISO 8601 timestamp (YYYY-MM-DDTHH:MM:SS), such as '2018', "
                  "'1999-03-21', or '2020-05-03 14:32:02'.\n\n Additionally, "
                  "you can give an integer time distance into the past, such "
                  "as '1 hour', '3months', or '2years'.(Whitepsace between "
                  "the number and unit is optuonal). Default: 30 days.")
        )
    def run(self, pav_cfg, args):
        """Run this command."""

        filter_func = None
        if not args.all:
            filter_func = filters.make_test_run_filter(
                older_than = args.older_than,
            )

        end = '\n' if args.verbose else '\r'

        # Clean Tests
        tests_dir = pav_cfg.working_dir / 'test_runs'     # type: Path
        output.fprint("Removing Tests...", file=self.outfile, end=end)
        try:
            rm_tests_count, msgs = clean.delete_tests(pav_cfg, tests_dir,
                                                      filter_func, args.verbose)
        except (ValueError, argparse.ArgumentError) as err:
            return errno.EINVAL
        if args.verbose:
            for msg in msgs:
                output.fprint(msg, color=output.YELLOW)
        output.fprint("Removed {} test(s).".format(rm_tests_count),
                      file=self.outfile, color=output.GREEN, clear=True)

        # Clean Series
        series_dir = pav_cfg.working_dir / 'series'       # type: Path
        output.fprint("Removing Series...", file=self.outfile, end=end)
        rm_series_count, msgs = clean.delete_series(series_dir, args.verbose)
        if args.verbose:
            for msg in msgs:
                output.fprint(msg, color=output.YELLOW)
        output.fprint("Removed {} series.".format(rm_series_count),
                      file=self.outfile, color=output.GREEN, clear=True)

        # Clean Builds
        builds_dir = pav_cfg.working_dir / 'builds'        # type: Path
        output.fprint("Removing Builds...", file=self.outfile, end=end)
        rm_builds_count, msgs = clean.delete_builds(builds_dir, tests_dir,
                                                    args.verbose)
        if args.verbose:
            for msg in msgs:
                output.fprint(msg, color=output.YELLOW)
        output.fprint("Removed {} build(s).".format(rm_builds_count),
                      file=self.outfile, color=output.GREEN, clear=True)

        return 0

