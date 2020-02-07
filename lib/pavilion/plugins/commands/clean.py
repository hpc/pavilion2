import errno
import os
import shutil
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
            'Clean up Pavilion working directory.',
            short_help="Clean up Pavilion working diretory."
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true', default=False,
            help='Verbose output.'
        )
        parser.add_argument(
            '--older-than', nargs='+', action='store',
            help='Set the max age of files to be removed. Can be a date ex:'
                 '"Jan 1 2019" or , or a number of days/weeks ex:"32 weeks"'
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
                cutoff_date = get_month_delta(int(args.older_than[0]))
            else:
                date = ' '.join(args.older_than)
                try:
                    cutoff_date = datetime.strptime(date, '%b %d %Y')
                except (TypeError, ValueError):
                    output.fprint("{} is not a valid date."
                                  .format(args.older_than),
                                  file=self.errfile, color=output.RED)
                    return errno.EINVAL

                    # No cutoff specified, removes everything.
        else:
            cutoff_date = datetime.today()

        tests_dir = pav_cfg.working_dir / 'test_runs'
        series_dir = pav_cfg.working_dir / 'series'
        download_dir = pav_cfg.working_dir / 'downloads'
        build_dir = pav_cfg.working_dir / 'builds'

        dependent_builds = []
        incomplete_tests = []
        # Clean Tests
        output.fprint("Removing Tests...", file=self.outfile,
                      color=output.GREEN)
        for test in os.listdir(tests_dir.as_posix()):
            test_time = datetime.fromtimestamp(
                os.path.getmtime((tests_dir / test).as_posix()))
            try:
                test_obj = TestRun.load(pav_cfg, int(test))
                status = test_obj.status.current().state
            except (TestRunError, TestRunNotFoundError):
                output.fprint("Removing bad test directory {}".format(test),
                              file=self.outfile)
                shutil.rmtree(tests_dir.as_posix())
                continue
            except PermissionError as err:
                err = str(err).split("'")
                output.fprint("Permission Error: {} cannot be removed"
                              .format(err[1]), file=self.errfile, color=31)
            if test_time < cutoff_date and status != STATES.RUNNING \
                    and status != STATES.SCHEDULED:
                shutil.rmtree((tests_dir / test).as_posix())
                if args.verbose:
                    output.fprint("Removed test {}".format(test),
                                  file=self.outfile)
            else:
                if args.verbose:
                    output.fprint("Skipped test {}".format(test),
                                  file=self.outfile)
                incomplete_tests.append(test)
                dependent_builds.append(test_obj.build_name)

        # Clean Series
        completed_series = True
        output.fprint("Removing Series...", file=self.outfile,
                      color=output.GREEN)
        for series in os.listdir(series_dir.as_posix()):
            try:
                series_time = datetime.fromtimestamp(
                    os.path.getmtime((series_dir / series).as_posix()))
                for test in incomplete_tests:
                    if os.path.exists((series_dir / series / test).as_posix()):
                        completed_series = False
                if series_time < cutoff_date and completed_series:
                    shutil.rmtree((series_dir / series).as_posix())
                    if args.verbose:
                        output.fprint("Removed series {}".format(series),
                                      file=self.outfile)
                else:
                    if args.verbose:
                        output.fprint("Skipped series {}".format(series),
                                      file=self.outfile)
            except PermissionError as err:
                err = str(err).split("'")
                output.fprint("Permission Error: {} cannot be removed"
                              .format(err[1]), file=self.errfile, color=31)

        # Clean Downloads
        output.fprint("Removing Downloads...", file=self.outfile,
                      color=output.GREEN)
        for download in os.listdir(download_dir.as_posix()):
            try:
                download_time = datetime.fromtimestamp(
                    os.path.getmtime((download_dir / download).as_posix()))
                if download_time < cutoff_date:
                    try:
                        shutil.rmtree((download_dir / download).as_posix())
                    except NotADirectoryError:
                        output.fprint("{} is not a directory.".format(download),
                                      file=self.errfile, color=output.RED)
                        os.remove((download_dir / download).as_posix())
                    if args.verbose:
                        output.fprint("Removed download {}".format(download),
                                      file=self.outfile)
                else:
                    if args.verbose:
                        output.fprint("Skipped download {}".format(download),
                                      file=self.outfile)
            except PermissionError as err:
                err = str(err).split("'")
                output.fprint("Permission Error: {} cannot be removed"
                              .format(err[1]), file=self.errfile, color=31)

        # Clean Builds
        output.fprint("Removing Builds...", file=self.outfile,
                      color=output.GREEN)
        for build in os.listdir(build_dir.as_posix()):
            try:
                build_time = datetime.fromtimestamp(
                    os.path.getmtime((build_dir / build).as_posix()))
                if build_time < cutoff_date and build not in dependent_builds:
                    shutil.rmtree((build_dir / build).as_posix())
                    if args.verbose:
                        output.fprint("Removed build {}".format(build),
                                      file=self.outfile)
                else:
                    if args.verbose:
                        output.fprint("Skipped build {}".format(build),
                                      file=self.outfile)
            except PermissionError as err:
                err = str(err).split("'")
                output.fprint("Permission Error: {} cannot be removed. "
                              .format(err[1]), file=self.errfile, color=31)

        return 0


def get_month_delta(months):
    """Turn a number of months in the future into a concrete date."""

    today = datetime.today()
    cur_year = today.year
    cur_day = today.day
    cur_month = today.month
    cur_time = today.time

    if cur_month - months <= 0:
        cut_month = (cur_month - months) % 12
        diff_years = (cur_month - months) // 12
        cut_year = cur_year + diff_years
    else:
        cut_month = cur_month - months
        cut_year = cur_year

    try:
        cutoff_date = datetime(cut_year, cut_month, cur_day, cur_time)
    except ValueError:
        last_day = monthrange(cut_year, cut_month)[1]
        cutoff_date = datetime(cut_year, cut_month, last_day, cur_time)

    return cutoff_date
