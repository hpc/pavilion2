import errno
import sys
import argparse
import os
import shutil
import time
from calendar import monthrange
from datetime import datetime, timedelta
from pavilion import commands
from pavilion import utils
from pavilion.pav_test import PavTest, PavTestError, PavTestNotFoundError
from pavilion.status_file import STATES


class CleanCommand(commands.Command):

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

    def run(self, pav_cfg, args, out_file=sys.stdout, err_file=sys.stderr):

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
                except (TypeError, ValueError) as err:
                    utils.fprint("{} is not a valid \
                                 date.".format(args.older_than),
                                 file=self.errfile, color=utils.RED)
                    return errno.EINVAL

        # No cutoff specified, removes everything.
        else:
            cutoff_date = datetime.today()

        tests_dir = pav_cfg.working_dir/'tests'
        series_dir = pav_cfg.working_dir/'series'
        download_dir = pav_cfg.working_dir/'downloads'
        build_dir = pav_cfg.working_dir/'builds'

        dependent_builds = []
        incomplete_tests = []
        # Clean Tests
        utils.fprint("Removing Tests...", file=self.outfile,
                     color=utils.GREEN)
        for test in os.listdir(tests_dir.as_posix()):
            test_time = datetime.fromtimestamp(
                os.path.getmtime((tests_dir/test).as_posix()))
            try:
                test_obj = PavTest.load(pav_cfg, int(test))
                status = test_obj.status.current().state
            except (PavTestError, PavTestNotFoundError) as err:
                utils.fprint("Removing bad test directory {}".format(test),
                             file=self.outfile)
                shutil.rmtree(tests_dir.as_posix())
                continue
            if test_time < cutoff_date and status != STATES.RUNNING \
                                       and status != STATES.SCHEDULED:
                shutil.rmtree((tests_dir/test).as_posix())
                if args.verbose:
                    utils.fprint("Removed test {}".format(test),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped test {}".format(test),
                                 file=self.outfile)
                incomplete_tests.append(test)
                dependent_builds.append(test_obj.build_name)

        # Clean Series
        completed_series = True
        utils.fprint("Removing Series...", file=self.outfile,
                     color=utils.GREEN)
        for series in os.listdir(series_dir.as_posix()):
            series_time = datetime.fromtimestamp(
                os.path.getmtime((series_dir/series).as_posix()))
            for test in incomplete_tests:
                if os.path.exists((series_dir/series/test).as_posix()):
                    completed_series = False
            if series_time < cutoff_date and completed_series:
                shutil.rmtree((series_dir/series).as_posix())
                if args.verbose:
                    utils.fprint("Removed series {}".format(series),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped series {}".format(series),
                                 file=self.outfile)

        # Clean Downloads
        utils.fprint("Removing Downloads...", file=self.outfile,
                     color=utils.GREEN)
        for download in os.listdir(download_dir.as_posix()):
            download_time = datetime.fromtimestamp(
                os.path.getmtime((download_dir/download).as_posix()))
            if download_time < cutoff_date:
                try:
                    shutil.rmtree(str(download_dir/download))
                except NotADirectoryError as err:
                    utils.fprint("{} is not a directory.".format(download),
                                 file=self.errfile, color=utils.RED)
                    os.remove(download)
                if args.verbose:
                    utils.fprint("Removed download {}".format(download),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped download {}".format(download),
                                 file=self.outfile)

        # Clean Builds
        utils.fprint("Removing Builds...", file=self.outfile, color=utils.GREEN)
        for build in os.listdir(build_dir.as_posix()):
            build_time = datetime.fromtimestamp(
                os.path.getmtime((build_dir/build).as_posix()))
            if build_time < cutoff_date and build not in dependent_builds:
                shutil.rmtree((build_dir/build).as_posix())
                if args.verbose:
                    utils.fprint("Removed build {}".format(build),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped build {}".format(build),
                                 file=self.outfile)

        return 0

def get_month_delta(months):

    cutoff_date = None
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
