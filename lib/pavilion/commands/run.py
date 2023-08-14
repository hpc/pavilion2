"""The run command resolves tests by their names, builds them, and runs them."""

import errno
import sys
from collections import defaultdict
from pathlib import Path


from pavilion import cmd_utils
from pavilion import groups
from pavilion import output
from pavilion.enums import Verbose
from pavilion.errors import TestSeriesError
from pavilion.series.series import TestSeries
from pavilion.series_config import generate_series_config
from pavilion.status_utils import print_from_tests
from .base_classes import Command


class RunCommand(Command):
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

    def _setup_arguments(self, parser):

        self._generic_arguments(parser)

        parser.add_argument(
            '-f', '--file', dest='files', action='append', default=[],
            help='One or more files to read to get the list of tests to run. '
                 'These files should contain a newline separated list of test '
                 'names. Lines that start with a \'#\' are ignored as '
                 'comments.')
        parser.add_argument(
            '--repeat', action='store', type=int, default=None,
            help='Repeat specified tests this many times.'
        )
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
            '-n', '--name', action='store', default=''
        )
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
                 'and value is a json object. Example: `-c schedule.nodes=23`')
        parser.add_argument(
            '-g', '--group', action="store", type=str,
            help="Add the created test series to the given group, creating it if necessary.")
        parser.add_argument(
            '-v', '--verbosity', choices=[verb.name for verb in Verbose],
            default=Verbose.DYNAMIC.name,
            help="Adjust the verbosity of the run command.\n"
                 " - QUIET   - Minimal output\n"
                 " - DYNAMIC - Dynamic status reporting. (default)\n"
                 " - HIGH    - Non-dynamic, high output.\n"
                 " - MAX     - Maximized output\n")
        parser.add_argument(
            '-i', '--ignore-errors', action='store_true', default=False,
            help="Ignore test creation, build and kickoff errors. Tests that "
                 "don't have errors will still run.")
        parser.add_argument(
            '-r', '--rebuild', action='store_true', default=False,
            help="Deprecate existing builds of these tests and rebuild. This "
                 "should be necessary only if the system or user environment "
                 "under which Pavilion runs has changed."
        )
        parser.add_argument(
            'tests', nargs='*', action='store', metavar='TEST_NAME',
            help='The name of the tests to run. These may be suite names (in '
                 'which case every test in the suite is run), or a '
                 '<suite_name>.<test_name>. Tests can be repeated explicitly '
                 'using a * notation that precedes or succeeds the test suite '
                 'or test name (i.e. 5*<suite_name> and <suite_name>*5 both '
                 'run every test in that suite 5 times).'
        )

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

        # Note: We have to get a few arguments this way because this code
        # is reused between the build and run commands, and the don't quite have the
        # same arguments.
        if args.name:
            series_name = args.name
        else:
            series_name = 'cmdline'

        series_cfg = generate_series_config(
            name=series_name,
            modes=args.modes,
            host=args.host,
            repeat=getattr(args, 'repeat', None),
            overrides=args.overrides,
            ignore_errors=args.ignore_errors,
        )

        tests = args.tests
        try:
            tests.extend(cmd_utils.read_test_files(pav_cfg, args.files))
        except ValueError as err:
            output.fprint(sys.stdout, "Error reading given test list files.\n{}"
                          .format(err))
            return errno.EINVAL

        local_builds_only = getattr(args, 'local_builds_only', False)
        report_status = getattr(args, 'status', False)

        # create brand-new series object
        series_obj = TestSeries(pav_cfg, series_cfg=series_cfg,
                                verbosity=Verbose[args.verbosity],
                                outfile=self.outfile)
        testset_name = cmd_utils.get_testset_name(args.tests, args.files)

        if args.group:
            try:
                group = groups.TestGroup(pav_cfg, args.group)
                group.add([series_obj])
            except groups.TestGroupError as err:
                output.fprint(self.errfile,
                              "Could not add series to group '{}'".format(args.group),
                              color=output.RED)
                output.fprint(self.errfile, err.pformat())
                return errno.EINVAL

        else:
            output.fprint(self.outfile, "Created Test Series {}.".format(series_obj.name))

        series_obj.add_test_set_config(
            testset_name,
            tests,
            modes=args.modes,
        )

        self.last_series = series_obj

        try:
            series_obj.run(
                build_only=self.BUILD_ONLY,
                rebuild=args.rebuild,
                local_builds_only=local_builds_only)
            self.last_tests = list(series_obj.tests.values())
        except TestSeriesError as err:
            self.last_tests = list(series_obj.tests.values())
            output.fprint(self.errfile, err, color=output.RED)
            return errno.EAGAIN

        if report_status:
            print_from_tests(
                pav_cfg=pav_cfg,
                tests=self.last_tests,
                outfile=self.outfile
            )

        return 0
