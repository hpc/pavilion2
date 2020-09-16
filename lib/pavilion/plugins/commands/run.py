"""The run command resolves tests by their names, builds them, and runs them."""

import errno
import pathlib
import threading
import subprocess
import os
import time
import argparse
from collections import defaultdict
from typing import List, Union

from pavilion import commands
from pavilion import output
from pavilion import result
from pavilion import schedulers
from pavilion import test_config
from pavilion import cmd_utils
from pavilion.builder import MultiBuildTracker
from pavilion.output import fprint
from pavilion.plugins.commands.status import print_from_tests
from pavilion.series import TestSeries, test_obj_from_id
from pavilion.status_file import STATES
from pavilion.test_run import TestRun, TestRunError, TestConfigError


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

        tests_by_sched = self._get_tests(
            pav_cfg, args, mb_tracker, build_only=self.BUILD_ONLY,
            local_builds_only=getattr(args, 'local_builds_only', False))
        if tests_by_sched is None:
            return errno.EINVAL

        all_tests = sum(tests_by_sched.values(), [])
        self.last_tests = list(all_tests)

        if not all_tests:
            fprint("You must specify at least one test.", file=self.errfile)
            return errno.EINVAL

        series = TestSeries(pav_cfg, all_tests)
        self.last_series = series

        res = self.check_result_format(all_tests)
        if res != 0:
            self.complete_tests(all_tests)
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
            self.complete_tests(all_tests)
            return res

        self.complete_tests([test for test in all_tests if
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

        return self.run_tests(
            pav_cfg=pav_cfg,
            tests_by_sched=tests_by_sched,
            series=series,
            wait=wait,
            report_status=report_status,
        )

    def run_tests(self, pav_cfg, tests_by_sched, series, wait, report_status):
        """
        :param pav_cfg:
        :param dict[str,[TestRun]] tests_by_sched: A dict by scheduler name
            of the tests (in a list).
        :param series: The test series.
        :param int wait: Wait this long for a test to start before exiting.
        :param bool report_status: Do a 'pav status' after tests have started.
            on nodes, and kick them off in build only mode.
        :return:
        """

        all_tests = sum(tests_by_sched.values(), [])

        for sched_name in tests_by_sched.keys():
            sched = schedulers.get_plugin(sched_name)

            if not sched.available():
                fprint("{} tests started with the {} scheduler, but "
                       "that scheduler isn't available on this system."
                       .format(len(tests_by_sched[sched_name]), sched_name),
                       file=self.errfile, color=output.RED)
                return errno.EINVAL

        for sched_name, tests in tests_by_sched.items():
            tests = [test for test in tests if not test.skipped]
            sched = schedulers.get_plugin(sched_name)

            # Filter out any 'build_only' tests (it should be all or none)
            # that shouldn't be scheduled.
            tests = [test for test in tests if
                     # The non-build only tests
                     (not test.build_only) or
                     # The build only tests that are built on nodes
                     (not test.build_local and
                      # As long they need to be built.
                      (test.rebuild or not test.builder.exists()))]

            # Skip this scheduler if it doesn't have tests that need to run.
            if not tests:
                continue

            try:
                sched.schedule_tests(pav_cfg, tests)
            except schedulers.SchedulerPluginError as err:
                fprint('Error scheduling tests:', file=self.errfile,
                       color=output.RED)
                fprint(err, bullet='  ', file=self.errfile)
                fprint('Cancelling already kicked off tests.',
                       file=self.errfile)
                self._cancel_all(tests_by_sched)
                # return so the rest of the tests don't actually run
                return errno.EINVAL

        # Tests should all be scheduled now, and have the SCHEDULED state
        # (at some point, at least). Wait until something isn't scheduled
        # anymore (either running or dead), or our timeout expires.
        wait_result = None
        if wait is not None:
            end_time = time.time() + wait
            while time.time() < end_time and wait_result is None:
                last_time = time.time()
                for sched_name, tests in tests_by_sched.items():
                    sched = schedulers.get_plugin(sched_name)
                    for test in tests:
                        status = test.status.current()
                        if status == STATES.SCHEDULED:
                            status = sched.job_status(pav_cfg, test)

                        if status != STATES.SCHEDULED:
                            # The test has moved past the scheduled state.
                            wait_result = None
                            break

                        break

                if wait_result is None:
                    # Sleep at most SLEEP INTERVAL seconds, minus the time
                    # we spent checking our jobs.
                    time.sleep(self.SLEEP_INTERVAL - (time.time() - last_time))

        fprint("{} test{} started as test series {}."
               .format(len(all_tests),
                       's' if len(all_tests) > 1 else '',
                       series.sid),
               file=self.outfile,
               color=output.GREEN)

        if report_status:
            tests = list(series.tests.keys())
            tests, _ = test_obj_from_id(pav_cfg, tests)
            return print_from_tests(
                pav_cfg=pav_cfg,
                tests=tests,
                outfile=self.outfile)

        return 0

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
        :rtype: {}
        """

        try:
            configs_by_sched = cmd_utils.get_test_configs(
                pav_cfg=pav_cfg,
                host=args.host,
                test_files=args.files,
                tests=args.tests,
                modes=args.modes,
                logger=self.logger,
                overrides=args.overrides,
                outfile=self.outfile)

            # Remove non-local builds when doing only local builds.
            if build_only and local_builds_only:
                for sched in configs_by_sched:
                    sched_cfgs = configs_by_sched[sched]
                    for i in range(len(sched_cfgs)):
                        config, _ = sched_cfgs[i]
                        if config['build']['on_nodes'].lower() == 'true':
                            sched_cfgs[i] = None
                    sched_cfgs = [cfg for cfg in sched_cfgs
                                  if cfg is not None]
                    configs_by_sched[sched] = sched_cfgs

            tests_by_sched = cmd_utils.configs_to_tests(
                pav_cfg=pav_cfg,
                configs_by_sched=configs_by_sched,
                mb_tracker=mb_tracker,
                build_only=build_only,
                rebuild=args.rebuild,
                outfile=self.outfile,
            )

        except commands.CommandError as err:
            fprint(err, file=self.errfile, flush=True)
            return None

        return tests_by_sched

    @staticmethod
    def _cancel_all(tests_by_sched):
        """Cancel each of the given tests using the appropriate scheduler."""
        for sched_name, tests in tests_by_sched.items():

            sched = schedulers.get_plugin(sched_name)

            for test in tests:
                sched.cancel_job(test)

    @staticmethod
    def complete_tests(tests):
        """Mark all of the given tests as complete. We generally do this after
        an error has been encountered, or if it was only built.
        :param [TestRun] tests: The tests to mark complete.
        """

        for test in tests:
            test.set_run_complete()

    def check_result_format(self, tests):
        """Make sure the result parsers for each test are ok."""

        rp_errors = []
        for test in tests:

            # Make sure the result parsers have reasonable arguments.
            try:
                result.check_config(test.config['result_parse'],
                                    test.config['result_evaluate'])
            except result.ResultError as err:
                rp_errors.append((test, str(err)))

        if rp_errors:
            fprint("Result Parser configurations had errors:",
                   file=self.errfile, color=output.RED)
            for test, msg in rp_errors:
                fprint(test.name, '-', msg, file=self.errfile)
            return errno.EINVAL

        return 0

