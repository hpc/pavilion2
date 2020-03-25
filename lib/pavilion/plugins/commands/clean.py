import errno
import os
import shutil
from pathlib import Path
from calendar import monthrange
from datetime import datetime, timedelta

from pavilion import output
from pavilion import commands
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
            '--older-than', nargs='+', action='store',
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

        if args.older_than:
            if 'day' in args.older_than or 'days' in args.older_than:
                cutoff_date = datetime.today() - timedelta(
                    days=int(args.older_than[0]))
            elif 'week' in args.older_than or 'weeks' in args.older_than:
                cutoff_date = datetime.today() - timedelta(
                    weeks=int(args.older_than[0]))
            elif 'month' in args.older_than or 'months' in args.older_than:
                cutoff_date = datetime.today() - timedelta(
                    days=30*int(args.older_than[0]))
            else:
                date = ' '.join(args.older_than)
                try:
                    cutoff_date = datetime.strptime(date, '%b %d %Y')
                except (TypeError, ValueError):
                    output.fprint("{} is not a valid date."
                                  .format(args.older_than),
                                  file=self.errfile, color=output.RED)
                    return errno.EINVAL
        elif args.all:
            cutoff_date = datetime.today()
        else:
            cutoff_date = datetime.today() - timedelta(days=30)

        tests_dir = pav_cfg.working_dir / 'test_runs'     # type: Path
        series_dir = pav_cfg.working_dir / 'series'       # type: Path
        download_dir = pav_cfg.working_dir / 'downloads'  # type: Path
        build_dir = pav_cfg.working_dir / 'builds'        # type: Path

        removed_tests = 0
        removed_series = 0
        removed_builds = 0
        removed_downloads = 0

        used_builds = set()

        # Clean Tests
        output.fprint("Removing Tests...", file=self.outfile,
                      color=output.GREEN)
        for test_path in tests_dir.iterdir():
            test = test_path.name
            try:
                int(test)
            except ValueError:
                # Skip files that aren't numeric
                continue

            # Skip non-directories.
            if not test_path.is_dir():
                continue

            try:
                test_time = datetime.fromtimestamp(test_path.lstat().st_mtime)
            except FileNotFoundError:
                # The file no longer exists. This is a race condition.
                continue

            build_origin_symlink = test_path/'build_origin'
            # 'None' will probably end up in used_builds, but that's ok.
            build_origin = None
            if (build_origin_symlink.exists() and
                    build_origin_symlink.is_symlink() and
                    build_origin_symlink.resolve().exists()):
                build_origin = build_origin_symlink.resolve()

            if test_time > cutoff_date:
                used_builds.add(build_origin)
                continue

            state = None
            try:
                test_obj = TestRun.load(pav_cfg, int(test))
                state = test_obj.status.current().state
            except (TestRunError, TestRunNotFoundError):
                # It's ok if this happens, we'll still remove by date.
                # It is possible the test isn't completely written (a race
                # condition).
                pass
            except PermissionError as err:
                err = str(err).split("'")
                output.fprint("Permission Error: {} cannot be removed"
                              .format(err[1]), file=self.errfile, color=31)
                continue

            if state in (STATES.RUNNING, STATES.SCHEDULED):
                used_builds.add(build_origin)
                continue

            try:
                shutil.rmtree(test_path.as_posix())
                if args.verbose:
                    output.fprint("Removed test {}".format(test_path),
                                  file=self.outfile)
                removed_tests += 1
            except OSError as err:
                output.fprint(
                    "Could not remove test {}: {}"
                    .format(test_path, err),
                    color=output.YELLOW, file=self.errfile)

        # Clean Series
        output.fprint("Removing Series...", file=self.outfile,
                      color=output.GREEN)
        for series in series_dir.iterdir():
            for test in series.iterdir():
                if (test.is_symlink() and
                        test.exists() and
                        test.resolve().exists()):
                    # This test is still present, so keep the series.
                    break
            else:
                # This series has no remaining tests, we can delete it.
                try:
                    shutil.rmtree(series.as_posix())
                    removed_series += 1
                except OSError as err:
                    output.fprint(
                        "Could not remove series {}: {}"
                        .format(series, err),
                        color=output.YELLOW, file=self.errfile
                    )

        # Clean Downloads
        output.fprint("Removing Downloads...", file=self.outfile,
                      color=output.GREEN)
        for download in download_dir.iterdir():
            try:
                download_time = datetime.fromtimestamp(
                    download.lstat().st_mtime)
                if download_time < cutoff_date:
                    if download.is_dir():
                        shutil.rmtree(download.as_posix())
                    else:
                        download.unlink()
                    removed_downloads += 1
                    if args.verbose:
                        output.fprint(
                            "Skipped download {}".format(download),
                            file=self.outfile)

            except OSError as err:
                output.fprint("Could not remove download {}: {}"
                              .format(download, err),
                              color=output.YELLOW, file=self.errfile)

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

        output.fprint("Removed {tests} tests, {series} series, {builds} "
                      "builds, and {downloads} downloads"
                      .format(tests=removed_tests, series=removed_series,
                              builds=removed_builds,
                              downloads=removed_downloads),
                      color=output.GREEN, file=self.outfile)
        return 0

