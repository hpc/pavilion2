"""Clean old tests/builds/etc from the working directory."""

from pathlib import Path

from pavilion import clean
from pavilion.config import PavConfig
from pavilion import filters
from pavilion import output
from pavilion.filters import const
from .base_classes import Command


class CleanCommand(Command):
    """Cleans outdated test and series run directories."""

    def __init__(self):
        super().__init__(
            'clean',
            "Clean up Pavilion working directory. Removes tests specified. "
            "Removes series and builds that don\'t correspond to any test "
            "runs(possibly because you just deleted those old runs).",
            short_help="Clean up Pavilion working directory."
        )

    def _setup_arguments(self, parser):
        parser.add_argument(
            '-v', '--verbose', action='store_true', default=False,
            help='Verbose output.'
        )
        filters.add_test_filter_args(parser)
        parser.add_argument(
            '-a', '--all', action='store_true',
            help='Attempts to remove everything in the working directory, '
                 'regardless of age.')

        parser.add_argument(
            '--label', action='store', default=None,
            help="Clean up the tests in the config area with this label.")

    def run(self, pav_cfg: PavConfig, args):
        """Run this command."""

        filter_func = None
        if not args.all:
            if args.filter is None:
                filter_func = const(True)
            else:
                filter_func = filters.parse_query(args.filter)

        end = '\n' if args.verbose else '\r'

        if args.label is not None:
            if args.label not in pav_cfg.configs:
                output.fprint(self.errfile, "")
            config_areas = [pav_cfg.configs[args.label]]
        else:
            config_areas = list(pav_cfg.configs.values())

        # Clean Tests
        for config_area in config_areas:
            working_dir = config_area['working_dir']

            tests_dir = working_dir / 'test_runs'     # type: Path
            output.fprint(self.outfile, "Removing Tests ({})".format(working_dir), end=end)
            rm_tests_count, msgs = clean.delete_tests(
                pav_cfg, tests_dir, filter_func, args.verbose)

            if args.verbose:
                for msg in msgs:
                    output.fprint(self.outfile, msg, color=output.YELLOW)
            output.fprint(self.outfile, "Removed {} test(s).".format(rm_tests_count),
                          color=output.GREEN, clear=True)

        # Clean Series
        series_dir = pav_cfg.working_dir / 'series'       # type: Path
        output.fprint(self.outfile, "Removing Series...", end=end)
        rm_series_count, msgs = clean.delete_series(pav_cfg, series_dir, args.verbose)
        if args.verbose:
            for msg in msgs:
                output.fprint(self.outfile, msg, color=output.YELLOW)
        output.fprint(self.outfile, "Removed {} series.".format(rm_series_count),
                      color=output.GREEN, clear=True)

        for config_area in config_areas:
            # Clean Builds
            working_dir = config_area['working_dir']
            builds_dir = working_dir / 'builds'        # type: Path
            tests_dir = working_dir / 'test_runs'
            output.fprint(self.outfile, "Removing Builds ({})".format(working_dir), end=end)
            rm_builds_count, msgs = clean.delete_unused_builds(pav_cfg, builds_dir, tests_dir,
                                                               args.verbose)
            msgs.extend(clean.delete_lingering_build_files(pav_cfg, builds_dir, tests_dir,
                                                           args.verbose))
            if args.verbose:
                for msg in msgs:
                    output.fprint(self.outfile, msg, color=output.YELLOW)
            output.fprint(self.outfile, "Removed {} build(s).".format(rm_builds_count),
                          color=output.GREEN, clear=True)


        deleted_groups, msgs = clean.clean_groups(pav_cfg)
        if args.verbose:
            for msg in msgs:
                output.fprint(self.outfile, msg, color=output.YELLOW)
        output.fprint(self.outfile,
                      "Removed {} test groups that became empty.".format(deleted_groups),
                      color=output.GREEN, clear=True)

        return 0
