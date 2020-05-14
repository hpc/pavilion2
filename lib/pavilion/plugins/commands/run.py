"""The run command resolves tests by their names, builds them, and runs them."""

import codecs
import errno
import pathlib
import time
import threading
from collections import defaultdict

from pavilion import commands
from pavilion import output
from pavilion.output import fprint
from pavilion import result_parsers
from pavilion import schedulers
from pavilion import system_variables
from pavilion import test_config
from pavilion.plugins.commands.status import print_from_test_obj
from pavilion.series import TestSeries, test_obj_from_id
from pavilion.status_file import STATES
from pavilion.test_run import TestRun, TestRunError, TestConfigError
from pavilion.builder import MultiBuildTracker


class RunCommand(commands.Command):
    """Resolve tests by name, build, and run them.

    :ivar TestSeries last_series: The suite number of the last suite to run
        with this command (for unit testing).
    :ivar [TestRun] last_tests: A list of the last test runs that this command
        started (also for unit testing).
    """

    BUILD_ONLY = False

    def __init__(self):

        super().__init__('run', 'Setup and run a set of tests.',
                         short_help="Setup and run a set of tests.")

        self.last_series = None
        self.last_tests = []

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
            '--series-id',
            help='Provide series ID if test is already part of a series.'
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

        if args.series_id is None:
            series = TestSeries(pav_cfg, all_tests)
        else:
            series = TestSeries.from_id(pav_cfg, args.series_id)
            series.add_tests(all_tests)

        self.last_series = series

        res = self.check_result_parsers(all_tests)
        if res != 0:
            self._complete_tests(all_tests)
            return res

        res = self.build_local(
            tests=all_tests,
            max_threads=pav_cfg.build_threads,
            mb_tracker=mb_tracker,
            build_verbosity=args.build_verbosity)
        if res != 0:
            self._complete_tests(all_tests)
            return res

        self._complete_tests([test for test in all_tests if
                              test.opts.build_only and test.build_local])

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
                     (not test.opts.build_only) or
                     # The build only tests that are built on nodes
                     (not test.build_local and
                      # As long they need to be built.
                      (test.opts.rebuild or not test.builder.exists()))]

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
                       series.id),
               file=self.outfile,
               color=output.GREEN)

        if report_status:
            tests = list(series.tests.keys())
            tests, _ = test_obj_from_id(pav_cfg, tests)
            return print_from_test_obj(
                pav_cfg=pav_cfg,
                test_obj=tests,
                outfile=self.outfile,
                json=False)

        return 0

    def _get_test_configs(self, pav_cfg, host, test_files, tests, modes,
                          overrides, sys_vars, conditions=None):
        """Translate a general set of pavilion test configs into the final,
        resolved configurations. These objects will be organized in a
        dictionary by scheduler, and have a scheduler object instantiated and
        attached.
        :param pav_cfg: The pavilion config
        :param str host: The host config to target these tests with
        :param list(str) modes: The mode configs to use.
        :param list(Path) test_files: Files containing a newline separated
            list of tests.
        :param list(str) tests: The tests to run.
        :param list(str) overrides: Overrides to apply to the configurations.
        :param Union[system_variables.SysVarDict,{}] sys_vars: The system
        variables dict.
        :returns: A dictionary (by scheduler type name) of lists of tuples
            test configs and their variable managers.
        """
        self.logger.debug("Finding Configs")

        resolver = test_config.TestConfigResolver(pav_cfg)

        tests = list(tests)
        for file in test_files:
            try:
                with pathlib.PosixPath(file).open() as test_file:
                    for line in test_file.readlines():
                        line = line.strip()
                        if line and not line.startswith('#'):
                            tests.append(line)
            except (OSError, IOError) as err:
                msg = "Could not read test file {}: {}".format(file, err)
                self.logger.error(msg)
                raise commands.CommandError(msg)

        resolved_cfgs = resolver.load(
            tests,
            host,
            modes,
            overrides,
            conditions=conditions
        )

        tests_by_scheduler = defaultdict(lambda: [])
        for cfg, var_man in resolved_cfgs:
            tests_by_scheduler[cfg['scheduler']].append((cfg, var_man))

        return tests_by_scheduler

    @staticmethod
    def _configs_to_tests(pav_cfg, configs_by_sched, mb_tracker=None,
                          build_only=False, rebuild=False):
        """Convert the dictionary of test configs by scheduler into actual
        tests.

        :param pav_cfg: The Pavilion config
        :param dict[str,list] configs_by_sched: A dictionary of lists of test
        configs.
        :param Union[MultiBuildTracker,None] mb_tracker: The build tracker.
        :param bool build_only: Whether to only build these tests.
        :param bool rebuild: After figuring out what build to use, rebuild it.
        :return:
        """

        tests_by_sched = {}

        for sched_name in configs_by_sched.keys():
            tests_by_sched[sched_name] = []
            try:
                for i in range(len(configs_by_sched[sched_name])):
                    cfg, var_man = configs_by_sched[sched_name][i]
                    tests_by_sched[sched_name].append(TestRun(
                        pav_cfg=pav_cfg,
                        config=cfg,
                        var_man=var_man,
                        build_tracker=mb_tracker,
                        build_only=build_only,
                        rebuild=rebuild,
                    ))
            except (TestRunError, TestConfigError) as err:
                raise commands.CommandError(err)

        return tests_by_sched

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

        sys_vars = system_variables.get_vars(True)

        try:
            configs_by_sched = self._get_test_configs(
                pav_cfg=pav_cfg,
                host=args.host,
                test_files=args.files,
                tests=args.tests,
                modes=args.modes,
                overrides=args.overrides,
                sys_vars=sys_vars,
            )

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

            tests_by_sched = self._configs_to_tests(
                pav_cfg=pav_cfg,
                configs_by_sched=configs_by_sched,
                mb_tracker=mb_tracker,
                build_only=build_only,
                rebuild=args.rebuild,
            )

        except commands.CommandError as err:
            # Our error messages get escaped to a silly degree
            err = codecs.decode(str(err), 'unicode-escape')
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
    def _complete_tests(tests):
        """Mark all of the given tests as complete. We generally do this after
        an error has been encountered, or if it was only built.
        :param [TestRun] tests: The tests to mark complete.
        """

        for test in tests:
            test.set_run_complete()

    def check_result_parsers(self, tests):
        """Make sure the result parsers for each test are ok."""

        rp_errors = []
        for test in tests:

            # Make sure the result parsers have reasonable arguments.
            try:
                result_parsers.check_args(test.config['results'])
            except TestRunError as err:
                rp_errors.append(str(err))

        if rp_errors:
            fprint("Result Parser configurations had errors:",
                   file=self.errfile, color=output.RED)
            for msg in rp_errors:
                fprint(msg, bullet=' - ', file=self.errfile)
            return errno.EINVAL

        return 0

    BUILD_STATUS_PREAMBLE = '{when:20s} {test_id:6} {state:{state_len}s}'
    BUILD_SLEEP_TIME = 0.1

    def build_local(self, tests, max_threads, mb_tracker,
                    build_verbosity):
        """Build all tests that request for their build to occur on the
        kickoff host.

        :param list[TestRun] tests: The list of tests to potentially build.
        :param int max_threads: Maximum number of build threads to start.
        :param int build_verbosity: How much info to print during building.
            See the -b/--build-verbose argument for more info.
        :param MultiBuildTracker mb_tracker: The tracker for all builds.
        """

        test_threads = []   # type: [(threading.Thread, None)]
        remote_builds = []

        cancel_event = threading.Event()

        # Generate new build names for each test that is rebuilding.
        # We do this here, even for non_local tests, because otherwise the
        # non-local tests can't tell what was built fresh either on a
        # front-end or by other tests rebuilding on nodes.
        for test in tests:
            if test.opts.rebuild and test.builder.exists():
                test.builder.deprecate()
                test.builder.rename_build()
                test.save_build_name()

        # We don't want to start threads that are just going to wait on a lock,
        # so we'll rearrange the builds so that the uniq build names go first.
        # We'll use this as a stack, so tests that should build first go at
        # the end of the list.
        build_order = []
        # If we've seen a build name, the build can go later.
        seen_build_names = set()

        for test in tests:
            if not test.build_local:
                remote_builds.append(test)
            elif test.builder.name not in seen_build_names:
                build_order.append(test)
                seen_build_names.add(test.builder.name)
            else:
                build_order.insert(0, test)

        # Keep track of what the last message printed per build was.
        # This is for double build verbosity.
        message_counts = {test.id: 0 for test in tests}

        # Used to track which threads are for which tests.
        test_by_threads = {}

        # The length of the last line printed when verbosity == 0.
        last_line_len = None

        if build_verbosity > 0:
            fprint(self.BUILD_STATUS_PREAMBLE
                   .format(when='When', test_id='TestID',
                           state_len=STATES.max_length, state='State'),
                   'Message', file=self.outfile, width=None)

        builds_running = 0
        # Run and track <max_threads> build threads, giving output according
        # to the verbosity level. As threads finish, new ones are started until
        # either all builds complete or a build fails, in which case all tests
        # are aborted.
        while build_order or test_threads:
            # Start a new thread if we haven't hit our limit.
            if build_order and builds_running < max_threads:
                test = build_order.pop()

                test_thread = threading.Thread(
                    target=test.build,
                    args=(cancel_event,)
                )
                test_threads.append(test_thread)
                test_by_threads[test_thread] = test
                test_thread.start()

            # Check if all our threads are alive, and join those that aren't.
            for i in range(len(test_threads)):
                thread = test_threads[i]
                if not thread.is_alive():
                    thread.join()
                    builds_running -= 1
                    test_threads[i] = None
                    test = test_by_threads[thread]

                    # Only output test status after joining a thread.
                    if build_verbosity == 1:
                        notes = mb_tracker.get_notes(test.builder)
                        when, state, msg = notes[-1]
                        when = output.get_relative_timestamp(when)
                        preamble = (self.BUILD_STATUS_PREAMBLE
                                    .format(when=when, test_id=test.id,
                                            state_len=STATES.max_length,
                                            state=state))
                        fprint(preamble, msg, wrap_indent=len(preamble),
                               file=self.outfile, width=None)

            test_threads = [thr for thr in test_threads if thr is not None]

            if cancel_event.is_set():
                for thread in test_threads:
                    thread.join()

                for test in build_order + remote_builds:
                    test.status.set(STATES.ABORTED,
                                    "Build aborted due to failures in other "
                                    "builds.")

                fprint("Build error while building tests. Cancelling runs.",
                       color=output.RED, file=self.outfile)

                for failed_build in mb_tracker.failures():
                    fprint(
                        "Build error for test {f.test.name} (#{f.test.id})."
                        .format(f=failed_build), file=self.errfile)
                    fprint(
                        "See test status file (pav cat {id} status) and/or "
                        "the test build log (pav log build {id})"
                        .format(id=failed_build.test.id), file=self.errfile)

                return errno.EINVAL

            state_counts = mb_tracker.state_counts()
            if build_verbosity == 0:
                # Print a self-clearing one-liner of the counts of the
                # build statuses.
                parts = []
                for state in sorted(state_counts.keys()):
                    parts.append("{}: {}".format(state, state_counts[state]))
                line = ' | '.join(parts)
                if last_line_len is not None:
                    fprint(' '*last_line_len, end='\r', file=self.outfile,
                           width=None)
                last_line_len = len(line)
                fprint(line, end='\r', file=self.outfile, width=None)
            elif build_verbosity > 1:
                for test in tests:
                    seen = message_counts[test.id]
                    msgs = mb_tracker.messages[test.builder][seen:]
                    for when, state, msg in msgs:
                        when = output.get_relative_timestamp(when)
                        state = '' if state is None else state
                        preamble = self.BUILD_STATUS_PREAMBLE.format(
                            when=when, test_id=test.id,
                            state_len=STATES.max_length, state=state)

                        fprint(preamble, msg, wrap_indent=len(preamble),
                               file=self.outfile, width=None)
                    message_counts[test.id] += len(msgs)

            time.sleep(self.BUILD_SLEEP_TIME)

        if build_verbosity == 0:
            # Print a newline after our last status update.
            fprint(width=None, file=self.outfile)

        return 0
