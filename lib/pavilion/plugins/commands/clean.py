from pavilion import commands
from pavilion import utils
import errno
import sys
import argparse
import os
import shutil
import time
from datetime import datetime, timedelta

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
            '2019" or , or a number of days/weeks/months ex:"32 weeks"'
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
                except TypeError as err:
                    utils.fprint("{} is not a valid date.".format(args.older_than))
                    return errno.EINVAL

        # No older than specified, removes everything.
        else:
            cutoff_date = datetime.today()

        tests_dir = pav_cfg.working_dir/'tests'
        series_dir = pav_cfg.working_dir/'series'
        download_dir = pav_cfg.working_dir/'downloads'
        build_dir = pav_cfg.working_dir/'builds'

        # Clean Tests
        utils.fprint("Removing Test Directories...", color=utils.GREEN)
        for test in os.listdir(str(tests_dir)):
            test_time = datetime.fromtimestamp(
                os.path.getmtime(str(tests_dir/test)))
            if test_time < cutoff_date:
                if args.verbose:
                    utils.fprint("Removed test {}".format(test))
                shutil.rmtree(str(tests_dir/test))

        # Clean Series
        utils.fprint("Removing Series Directories...", color=utils.GREEN)
        for series in os.listdir(str(series_dir)):
            series_time = datetime.fromtimestamp(
                os.path.getmtime(str(series_dir/series)))
            if series_time < cutoff_date:
                if args.verbose:
                    utils.fprint("Removed series {}".format(series))
                shutil.rmtree(str(series_dir/series))

        # Clean Downloads
        utils.fprint("Removing Download Directories...", color=utils.GREEN)
        for download in os.listdir(str(download_dir)):
            download_time = datetime.fromtimestamp(
                os.path.getmtime(str(download_dir/download)))
            if download_time < cutoff_date:
                if args.verbose:
                    utils.fprint("Removed download {}".format(download))
                shutil.rmtree(str(download_dir/download))

        # Clean Builds
        utils.fprint("Removing Builds...", color=utils.GREEN)
        for build in os.listdir(str(build_dir)):
            build_time = datetime.fromtimestamp(
                os.path.getmtime(str(build_dir/build)))
            if build_time < cutoff_date:
                if args.verbose:
                    utils.fprint("Removed build {}".format(build))
                shutil.rmtree(str(build_dir/build))

        return 0

