"""Clean old tests/builds/etc from the working directory."""

from pathlib import Path

from pavilion import clean
from pavilion import commands
from pavilion import filters
from pavilion import output


class CleanCommand(commands.Command):
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
        ),
        filters.add_test_filter_args(parser)
        parser.add_argument(
            '-a', '--all', action='store_true',
            help='Attempts to remove everything in the working directory, '
                 'regardless of age.'
        )

    def run(self, pav_cfg, args):
        """Run this command."""

        filter_func = None
        if not args.all:
            filter_func = filters.make_test_run_filter(
                complete=args.complete,
                failed=args.failed,
                incomplete=args.incomplete,
                name=args.name,
                newer_than=args.newer_than,
                older_than=args.older_than,
                passed=args.passed,
                result_error=args.result_error,
                show_skipped=args.show_skipped,
                sys_name=args.sys_name,
                user=args.user
            )

        end = '\n' if args.verbose else '\r'

        # Clean Tests
        tests_dir = pav_cfg.working_dir / 'test_runs'     # type: Path
        output.fprint("Removing Tests...", file=self.outfile, end=end)
        rm_tests_count, msgs = clean.delete_tests(tests_dir, filter_func,
                                                  args.verbose)
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
