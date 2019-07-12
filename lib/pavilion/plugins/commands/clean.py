from pavilion import commands
from pavilion import utils
import errno
import sys
import argparse
import os
import shutil
import time
from datetime import datetime, timedelta
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
            help='Set the max age of files to be removed. Can be a date ex:"Jan 1 '
            '2019" or , or a number of days/weeks ex:"32 weeks"'
        )

    def run(self, pav_cfg, args):

        if args.older_than:
            if 'day' in args.older_than or 'days' in args.older_than:
                cutoff_date = datetime.today() - timedelta(
                    days=int(args.older_than[0]))
            elif 'week' in args.older_than or 'weeks' in args.older_than:
                cutoff_date = datetime.today() - timedelta(
                    weeks=int(args.older_than[0]))
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
        utils.fprint("Removing Test Directories...", file=self.outfile,
                     color=utils.GREEN)
        for test in os.listdir(str(tests_dir)):
            test_time = datetime.fromtimestamp(
                os.path.getmtime(str(tests_dir/test)))
            try:
                test_obj = PavTest.load(pav_cfg, int(test))
                status = test_obj.status.current().state
            except (PavTestError, PavTestNotFoundError, KeyError) as err:
                utils.fprint("Removing bad test directory {}".format(test),
                             file=self.outfile)
                shutil.rmtree(str(tests_dir/test))
                continue
            if test_time < cutoff_date and status != STATES.RUNNING \
                                       and status != STATES.SCHEDULED:
                shutil.rmtree(str(tests_dir/test))
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
        utils.fprint("Removing Series Directories...", file=self.outfile,
                     color=utils.GREEN)
        for series in os.listdir(str(series_dir)):
            series_time = datetime.fromtimestamp(
                os.path.getmtime(str(series_dir/series)))
            for test in incomplete_tests:
                if os.path.exists(str(series_dir/series/test)):
                    completed_series = False
            if series_time < cutoff_date and completed_series:
                shutil.rmtree(str(series_dir/series))
                if args.verbose:
                    utils.fprint("Removed series {}".format(series),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped series {}".format(series),
                                 file=self.outfile)

        # Clean Downloads
        utils.fprint("Removing Download Directories...", file=self.outfile,
                     color=utils.GREEN)
        for download in os.listdir(str(download_dir)):
            download_time = datetime.fromtimestamp(
                os.path.getmtime(str(download_dir/download)))
            if download_time < cutoff_date:
                try:
                    shutil.rmtree(str(download_dir/download))
                except NotADirectoryError as err:
                    utils.fprint("{} is not a directory.".format(download),
                                 file=self.errfile, color=utils.RED)
                    try:
                        os.remove(download)
                    except FileNotFoundError as err:
                        utils.fprint("{} could not be found.".format(download),
                                    file=self.errfile, color=utils.RED)
                        continue
                if args.verbose:
                    utils.fprint("Removed download {}".format(download),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped download {}".format(download),
                                 file=self.outfile)

        # Clean Builds
        utils.fprint("Removing Builds...", file=self.outfile, color=utils.GREEN)
        for build in os.listdir(str(build_dir)):
            build_time = datetime.fromtimestamp(
                os.path.getmtime(str(build_dir/build)))
            if build_time < cutoff_date and build not in dependent_builds:
                shutil.rmtree(str(build_dir/build))
                if args.verbose:
                    utils.fprint("Removed build {}".format(build),
                                 file=self.outfile)
            else:
                if args.verbose:
                    utils.fprint("Skipped build {}".format(build),
                                 file=self.outfile)

        return 0

