"""The run command resolves tests by their names, builds them, and runs them."""

import errno
from typing import List

from pavilion import cmd_utils
from pavilion import commands
from pavilion import output
from pavilion import schedulers
from pavilion import status_utils
from pavilion.build_tracker import MultiBuildTracker
from pavilion.output import fprint
from pavilion.series import TestSeries
from pavilion.test_run import TestRun


class RunCommand(commands.Command):
    """Resolve tests by name, build, and run them.

    :ivar TestSeries last_series: The suite number of the last suite to run
        with this command (for unit testing).
    :ivar List[TestRun] last_tests: A list of the last test runs that this
        command started (also for unit testing).
    """

    BUILD_ONLY = False

    def __init__(self):

        super().__init__('run', 'Setup and run a set of tests.',
                         short_help="Setup and run a set of tests.")

        self.last_series = None
        self.last_tests = []  # type: List[TestRun]

    def _setup_arguments(self, parser):

        self._generic_arguments(parser)

        parser.add_argument(
            '-w', '--wait', action='store', type=int, default=None,
            help='Wait this many seconds to make sure at least one test '
                 'started before returning. If a test hasn\'t started by '
                 'then, cancel all tests and return a failure. Defaults to'
                 'not checking tests before returning.'
        )
        parser.add_argument(
            '-f', '--file', dest='files', action='append', default=[],
            help='One or more files to read to get the list of tests to run. '
                 'These files should contain a newline separated list of test '
                 'names. Lines that start with a \'#\' are ignored as '
                 'comments.')
        parser.add_argument(
            '-s', '--status', action='store_true', default=False,
            help='Display test statuses'
        )

    @staticmethod
    def _generic_arguments(parser):
        """Setup the generic arguments for the run command. We break this out
        because the build and run commands are the same, but have slightly
        different args.

        :param argparse.ArgumentParser parser:
        """

        parser.add_argument(
            '-H', '--host', action='store',
            help='The host to configure this test for. If not specified, the '
                 'current host as denoted by the sys plugin \'sys_host\' is '
                 'used.')
        parser.add_argument(
            '-m', '--mode', action='append', dest='modes', default=[],
            help='Mode configurations to overlay on the host configuration for '
                 'each test. These are overlayed in the order given.')
        parser.add_argument(
            '-c', dest='overrides', action='append', default=[],
            help='Overrides for specific configuration options. These are '
                 'gathered used as a final set of overrides before the '
                 'configs are resolved. They should take the form '
                 '\'key=value\', where key is the dot separated key name, '
                 'and value is a json object.')
        parser.add_argument(
            '-b', '--build-verbose', dest='build_verbosity', action='count',
            default=0,
            help="Increase the verbosity when building. By default, the "
                 "count of current states for the builds is printed. If this "
                 "argument is included once, the final status and note for "
                 "each build is printed. If this argument is included more"
                 "than once, every status change for each build is printed. "
                 "This only applies for local builds; refer to the build log "
                 "for information on 'on_node' builds."
        )
        parser.add_argument(
            '-r', '--rebuild', action='store_true', default=False,
            help="Deprecate existing builds of these tests and rebuild. This "
                 "should be necessary only if the system or user environment "
                 "under which Pavilion runs has changed."
        )
        parser.add_argument(
            'tests', nargs='*', action='store',
            help='The name of the tests to run. These may be suite names (in '
                 'which case every test in the suite is run), or a '
                 '<suite_name>.<test_name>.')

    SLEEP_INTERVAL = 1

    def run(self, pav_cfg, args):
        """Resolve the test configurations into individual tests and assign to
        schedulers. Have those schedulers kick off jobs to run the individual
        tests themselves.
        :param pav_cfg: The pavilion configuration.
        :param args: The parsed command line argument object.
        """
        # 1. Resolve the test configs
        #   - Get sched vars from scheduler.
        #   - Compile variables.
        #

        mb_tracker = MultiBuildTracker()

        local_builds_only = getattr(args, 'local_builds_only', False)

        test_list = self._get_tests(
            pav_cfg, args, mb_tracker, build_only=self.BUILD_ONLY,
            local_builds_only=getattr(args, 'local_builds_only', False))
        if test_list is None:
            return errno.EINVAL

        all_tests = test_list
        self.last_tests = all_tests

        if not all_tests:
            fprint("You must specify at least one test.", file=self.errfile)
            return errno.EINVAL

        series = TestSeries(pav_cfg, all_tests)
        self.last_series = series

        res = cmd_utils.check_result_format(all_tests, self.errfile)
        if res != 0:
            cmd_utils.complete_tests(all_tests)
            return res

        all_tests = [test for test in all_tests if not test.skipped]

        res = cmd_utils.build_local(
            tests=all_tests,
            max_threads=pav_cfg.build_threads,
            mb_tracker=mb_tracker,
            build_verbosity=args.build_verbosity,
            outfile=self.outfile,
            errfile=self.errfile)
        if res != 0:
            cmd_utils.complete_tests(all_tests)
            return res

        cmd_utils.complete_tests([test for test in all_tests if
                                 test.build_only and test.build_local])

        wait = getattr(args, 'wait', None)
        report_status = getattr(args, 'status', False)

        if self.BUILD_ONLY and local_builds_only:
            non_local_build_tests = [test for test in all_tests
                                     if not test.build_local]
            if non_local_build_tests:
                fprint(
                    "Skipping tests that are set to build on nodes: {}"
                    .format([test.name for test in non_local_build_tests]),
                    file=self.outfile, color=output.YELLOW)
            return 0

        res = series.run_tests(wait=wait)

        if report_status:
            status_utils.print_from_tests(
                pav_cfg=pav_cfg,
                tests=all_tests,
                outfile=self.outfile)

        return res

    def _get_tests(self, pav_cfg, args, mb_tracker, build_only=False,
                   local_builds_only=False):
        """Turn the test run arguments into actual TestRun objects.
        :param pav_cfg: The pavilion config object
        :param args: The run command arguments
        :param MultiBuildTracker mb_tracker: The build tracker.
        :param bool build_only: Whether to denote that we're only building
            these tests.
        :param bool local_builds_only: Only include tests that would be built
            locally.
        :return:
        :rtype: []
        """

        try:
            test_configs = cmd_utils.get_test_configs(pav_cfg=pav_cfg,
                                                      host=args.host,
                                                      test_files=args.files,
                                                      tests=args.tests,
                                                      modes=args.modes,
                                                      overrides=args.overrides,
                                                      outfile=self.outfile)

            # Remove non-local builds when doing only local builds.
            if build_only and local_builds_only:
                locally_built_tests = []
                for ptest in test_configs:
                    if ptest.config['build']['on_nodes'].lower() != 'true':
                        locally_built_tests.append(ptest)

                test_configs = locally_built_tests

            test_list = cmd_utils.configs_to_tests(
                pav_cfg=pav_cfg,
                proto_tests=test_configs,
                mb_tracker=mb_tracker,
                build_only=build_only,
                rebuild=args.rebuild,
                outfile=self.outfile,
            )

        except commands.CommandError as err:
            fprint(err, file=self.errfile, flush=True)
            return None

        return test_list

    @staticmethod
    def _cancel_all(tests_by_sched):
        """Cancel each of the given tests using the appropriate scheduler."""
        for sched_name, tests in tests_by_sched.items():

            sched = schedulers.get_plugin(sched_name)

            for test in tests:
                sched.cancel_job(test)
