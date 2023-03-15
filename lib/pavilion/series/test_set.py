"""Test sets translate the specifications of which tests to run (with which options),
into a set of ready to run tests. They are ephemeral, and are not tracked between
Pavilion runs."""
import io
import os
import threading
import time
from collections import defaultdict
from io import StringIO
from typing import List, Dict, TextIO, Union, Set, Iterator, Tuple

import pavilion.errors
from pavilion import output, result, schedulers, cancel_utils
from pavilion.build_tracker import MultiBuildTracker
from pavilion.errors import TestRunError, TestConfigError, TestSetError, ResultError
from pavilion.resolver import TestConfigResolver
from pavilion.status_file import SeriesStatusFile, STATES, SERIES_STATES
from pavilion.test_run import TestRun
from pavilion.utils import str_bool
from pavilion.enums import Verbose
from pavilion.jobs import Job

S_STATES = SERIES_STATES


class TestSet:
    """A set of tests given a set of test configuration options. In general,
    setting up a test set involves the following steps:

    - Init: test_set = TestSet()
    - Test Construction: test_set.make_tests()
    - Test Building: test_set.build_local()
    - Kickoff: test_set.kickoff()
    """

    # need info like
    # modes, only/not_ifs, next, prev
    def __init__(self,
                 pav_cfg,
                 name: str,
                 test_names: List[str],
                 iteration: int = 0,
                 status: SeriesStatusFile = None,
                 modes: List[str] = None,
                 host: str = None,
                 sys_os: str = None,
                 only_if: Dict[str, List[str]] = None,
                 not_if: Dict[str, List[str]] = None,
                 overrides: List = None,
                 parents_must_pass: bool = False,
                 simultaneous: Union[int, None] = None,
                 ignore_errors: bool = False,
                 outfile: TextIO = StringIO(),
                 verbosity=Verbose.QUIET):
        """Initialize the tests given these options, creating TestRun objects.

        :param pav_cfg: The Pavilion configuration.
        :param name: The name of this test set.
        :param test_names: A list of test/suite names.
        :param iteration: Which 'repeat' iteration this test set represents.
        :param modes: Modes to apply to all tests.
        :param host: Host configuration name to run under.
        :param only_if: Global 'only_if' conditions.
        :param not_if: Global 'not_if' conditions.
        :param overrides: Configuration overrides.
        :param parents_must_pass: Parent test sets must pass for this test set to run.
        :param status: A file-like object to log status and error messages to.
        :param simultaneous: The maximum number of test to start at the same time.
        :param ignore_errors: Whether to raise encountered errors or just continue.
        :param outfile: Where to send user output.
        :param verbosity: The build verbosity, see pavilion.enums.Verbose.
        """

        if status is not None:
            self.status = status
        else:
            self.status = SeriesStatusFile(None)

        self.name = name
        self.iter_name = '{}.{}'.format(iteration, name)
        self.verbosity = verbosity
        self.outfile = outfile
        self.ignore_errors = ignore_errors

        self.simultaneous = 2**32 if simultaneous is None else simultaneous
        self.batch_size = max(self.simultaneous//2, 1)

        self.modes = modes or []
        self.host = host
        self.sys_os = sys_os
        self.only_if = only_if or {}
        self.not_if = not_if or {}
        self.pav_cfg = pav_cfg
        self.overrides = overrides or []

        self.parent_sets = set()  # type: Set[TestSet]
        self.child_sets = set()  # type: Set[TestSet]
        self.parents_must_pass = parents_must_pass

        self.tests: List[TestRun] = []
        self.all_tests_made = False
        self.ready_to_build: List[TestRun] = []
        self.ready_to_start: List[TestRun] = []
        self.started_tests: List[TestRun] = []
        self.completed_tests: List[TestRun] = []

        # A dictionary of test set info, written to the set info file.
        self._info = {}

        self._should_run = None
        self._test_names = test_names
        self.mb_tracker = MultiBuildTracker()
        self.status.set(S_STATES.SET_CREATED,
                        "Created test set {}.".format(self.name))

    def add_parents(self, *parents: 'TestSet'):
        """Add the given TestSets as a parent to this one."""

        for parent in parents:
            self.parent_sets.add(parent)
            parent.child_sets.add(self)

    def remove_parent(self, parent: 'TestSet'):
        """Remove the given parent from this test set."""

        try:
            self.parent_sets.remove(parent)
        except KeyError:
            pass

        try:
            parent.child_sets.remove(self)
        except KeyError:
            pass

    # This was written by mistake, but may be useful in the future.
    # pylint: disable=unused-private-member
    def __ordered_split(self) -> List['TestSet']:
        """Split this TestSet into multiple test sets, such that each set depends on
        the last and the tests run in the order given."""

        if self.tests:
            raise RuntimeError("You can't split a TestSet once it's tests have been"
                               "created.")

        # For empty or single test_name test sets, we don't need to do anything.
        if len(self._test_names) < 2:
            return [self]

        test_sets = []

        # Create a new test set for all but the last test name.
        for i in range(len(self._test_names) - 1):
            test_sets.append(TestSet(
                pav_cfg=self.pav_cfg,
                name="{}.{}".format(self.name, i),
                test_names=[self._test_names[i]],
                status=self.status,
                modes=self.modes,
                host=self.host,
                pav_os=self.sys_os,
                only_if=self.only_if,
                not_if=self.not_if,
                overrides=self.overrides))
            i += 1

        # Modify this test set so that it only includes the last test name,
        # and add it to our list.
        self.name = "{}.{}".format(self.name, len(self._test_names))
        self._test_names = [self._test_names[-1]]
        test_sets.append(self)

        orig_parents = self.parent_sets.copy()

        # Adjust the parents of each test set (except the first) to include the
        # previous test in the list.
        for i in range(1, len(test_sets)):
            test_sets[i].add_parents(test_sets[i - 1])
            # Only the first set should depend on prior sets passing.
            test_sets[i].parents_must_pass = False

        # Point the original parents at the new first test set.
        for parent in orig_parents:
            test_sets[0].add_parents(parent)
            test_sets[-1].remove_parent(parent)

        return test_sets

    def make_iter(self, build_only=False, rebuild=False, local_builds_only=False) \
                  -> Iterator[List[TestRun]]:
        """Resolve the given tests names and options into actual test run objects, and print
        the test creation status.  This returns an iterator over batches tests, respecting the
        batch_size (half the simultanious limit).
        """

        self.status.set(S_STATES.SET_MAKE, "Setting up TestRun creation.")

        global_conditions = {
            'only_if': self.only_if,
            'not_if': self.not_if
        }

        cfg_resolver = TestConfigResolver(self.pav_cfg, host=self.host, outfile=self.outfile,
                                          verbosity=self.verbosity)

        self.status.set(S_STATES.SET_MAKE,
                        "Resolving {} test requests in sets of {} (half the simultaneous limit)."
                        .format(len(self._test_names), self.batch_size))

        for test_batch in cfg_resolver.load_iter(
                self._test_names,
                self.modes,
                self.sys_os,
                self.overrides,
                conditions=global_conditions,
                batch_size=self.batch_size,):

            if cfg_resolver.errors:
                output.fprint(
                    self.outfile,
                    "Error loading test configs for test set '{}'".format(self.name))

                for error in cfg_resolver.errors:
                    self.status.set(S_STATES.ERROR,
                                    '{} - {}'.format(error.request.request, error.pformat()))

                    output.fprint(
                        self.outfile,
                        "{} - {}".format(error.request.request, error.pformat()))

                if not self.ignore_errors:
                    raise TestSetError("Error creating tests for test set {}.".format(self.name),
                                       cfg_resolver.errors[0])

            self.status.set(S_STATES.SET_MAKE, "Creating {} test runs".format(len(test_batch)))

            progress = 0
            skip_count = 0

            new_test_runs = []
            for ptest in test_batch:
                if self.verbosity == Verbose.DYNAMIC:
                    progress += 1.0 / len(test_batch)
                    output.fprint(self.outfile, "Creating Test Runs: {:.0%}".format(progress),
                                  end='\r')

                if build_only and local_builds_only:
                    # Don't create test objects for tests that would build remotely.
                    if str_bool(ptest.config.get('build', {}).get('on_nodes', 'False')):
                        skip_count += 1
                        self.status.set(
                            S_STATES.TESTS_SKIPPED,
                            "Skipped test named '{}' from series '{}' - We're just "
                            "building locally, and this test builds only on nodes."
                            .format(ptest.config.get('name'), ptest.config.get('suite')))
                        continue

                try:
                    test_run = TestRun(pav_cfg=self.pav_cfg, config=ptest.config,
                                       var_man=ptest.var_man, rebuild=rebuild,
                                       build_only=build_only)
                    if not test_run.skipped:
                        test_run.save()
                        self.tests.append(test_run)
                        new_test_runs.append(test_run)

                        if self.verbosity in (Verbose.HIGH, Verbose.MAX):
                            output.fprint(self.outfile, 'Created and saved test run {} - {}'
                                                   .format(test_run.full_id, test_run.name))
                    else:
                        skip_count += 1
                        msg = "{} - {}" \
                              .format(test_run.name, test_run.skip_reasons[0])
                        self.status.set(S_STATES.TESTS_SKIPPED, msg)
                        if self.verbosity in (Verbose.MAX, Verbose.HIGH):
                            output.fprint(self.outfile, msg)

                        if not test_run.abort_skipped():
                            self.status.set(
                                S_STATES.TESTS_SKIPPED,
                                "Cleanup of skipped test {} was unsuccessful.")

                except (TestRunError, TestConfigError) as err:
                    tcfg = ptest.config
                    test_name = "{}.{}".format(tcfg.get('suite'), tcfg.get('name'))
                    msg = ("Error creating test '{}' in test set '{}'"
                           .format(test_name, self.name))
                    self.status.set(S_STATES.ERROR, msg + ': ' + str(err.args[0]))
                    if self.ignore_errors:
                        if self.verbosity in (Verbose.MAX, Verbose.HIGH):
                            output.fprint(self.outfile, msg)
                    else:
                        self.cancel("Error creating other tests in test set '{}'"
                                    .format(self.name))
                        raise TestSetError(msg, err)

            if self.verbosity == Verbose.DYNAMIC:
                output.fprint(self.outfile, '')

            self.status.set(
                S_STATES.SET_MAKE,
                "Test set '{}' created {} more tests, skipped {}"
                .format(self.name, len(new_test_runs), skip_count))

            output.fprint(
                self.outfile,
                "Test set '{}' created {} tests, skipped {}, {} errors\n"
                "To see why each test was skipped, run:\n"
                "`pav series states --skipped`"
                .format(self.name, len(self.tests), skip_count,
                        len(cfg_resolver.errors)))

            if new_test_runs:
                self.ready_to_build.extend(new_test_runs)
                yield new_test_runs

        self.all_tests_made = True


    def make(self, build_only=False, rebuild=False, local_builds_only=False):
        """As per make_iter(), but create all of the tests. This doesn't
        respect batch sizes, etc, and is entirely for simplifying unit testing."""

        all_tests = []
        for test_batch in self.make_iter(build_only, rebuild, local_builds_only):
            all_tests.extend(test_batch)

        return all_tests


    BUILD_STATUS_PREAMBLE = '{when:20s} {test_id:6} {state:{state_len}s}'
    BUILD_SLEEP_TIME = 0.1

    def build(self, deprecated_builds: Union[Set[str], None] = None,
              failed_builds: Union[Dict[str, str], None] = None) -> List[TestRun]:
        """Build the tests in this Test Set in parallel. This handles user output
        during the build process. Returns all the successfully built tests.

        :param tests: The new tests to build.
        :param deprecated_builds: A list of builds that have been deprecated
            by the calling series already, so we don't do it again.
        :param failed_builds: Builds we've already tried, but have failed.
        """

        deprecated_builds = set() if deprecated_builds is None else deprecated_builds
        failed_builds = dict() if failed_builds is None else failed_builds

        self.status.set(S_STATES.SET_BUILD, "Building {} tests fo test set {}"
                                            .format(len(self.ready_to_build), self.iter_name))

        output.fprint(self.outfile, "Building {} tests for test set {}."
                      .format(len(self.ready_to_build), self.name))

        # Tests to build now
        local_builds = list(filter(lambda t: t.build_local, self.ready_to_build))
        # Tests that will build on nodes.
        remote_builds = list(filter(lambda t: not t.build_local, self.ready_to_build))

        self.ready_to_build = []

        # Tests that were successfully built.
        built_tests: List[TestRun] = []

        test_threads: List[Union[threading.Thread, None]] = []

        # Generate new build names for each test that is rebuilding.
        # We do this here, even for non_local builds, because otherwise the
        # non-local builds can't tell what was built fresh either on a
        # front-end or by other tests rebuilding on nodes.
        for test in local_builds + remote_builds:
            if test.rebuild and test.builder.exists():
                if test.builder.name not in deprecated_builds:
                    deprecated_builds.add(test.builder.name)
                    test.builder.deprecate()

                test.builder.rename_build()
                test.build_name = test.builder.name
                test.save_attributes()

        build_names = set([test.builder.name for test in local_builds])
        if self.ignore_errors:
            # Each unique build name will share a cancel event.
            cancel_events = {name: threading.Event() for name in build_names}
        else:
            # All builds share a cancel event.
            single_cancel_event = threading.Event()
            cancel_events = {name: single_cancel_event for name in build_names}

        # We don't want to start threads that are just going to wait on a lock,
        # so we'll rearrange the builds so that the unique build names go first.
        # We'll use this as a stack, so tests that should build first go at
        # the end of the list.
        build_order = []
        # If we've seen a build name, the build can go later.
        seen_build_names = set()

        trackers = {}

        for test in local_builds:
            if test.builder.name not in seen_build_names:
                build_order.append(test)
                seen_build_names.add(test.builder.name)
            else:
                build_order.insert(0, test)

        # Create thread safe status trackers for each test.
        for test in local_builds:
            tracker = self.mb_tracker.register(test)
            trackers[test] = tracker

        # Keep track of what the last message printed per build was.
        # This is for double build verbosity.
        message_counts = {test.full_id: 0 for test in local_builds}

        # Used to track which threads are for which tests.
        test_by_threads = {}

        if self.verbosity not in (Verbose.QUIET, Verbose.DYNAMIC):
            output.fprint(self.outfile, self.BUILD_STATUS_PREAMBLE.format(
                when='When', test_id='TestID',
                state_len=STATES.max_length, state='State'), 'Message', width=None)

        builds_running = 0
        # Run and track <max_threads> build threads, giving output according
        # to the verbosity level. As threads finish, new ones are started until
        # either all builds complete or a build fails, in which case all tests
        # are aborted.
        while build_order or test_threads:
            # Start a new thread if we haven't hit our limit.
            if build_order and builds_running < self.pav_cfg.build_threads:
                test = build_order.pop()
                cancel_event = cancel_events[test.builder.name]

                if test.builder.name in failed_builds:
                    if self.verbosity in (Verbose.HIGH, Verbose.MAX):
                        output.fprint(self.outfile,
                                      "Skipping build for test {} - prior attempts failed."
                                      .format(test.full_id))
                    test.status.set(STATES.BUILD_FAILED,
                                    "Build failed when being built for test {} (they "
                                    "share a build.".format(failed_builds[test.builder.name]))
                    test.set_run_complete()
                    continue

                test_thread = threading.Thread(
                    target=test.build,
                    args=(cancel_event, trackers[test])
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
                    del test_by_threads[thread]
                    cancel_event = cancel_events[test.builder.name]

                    # Add this test to our list of succesfully built tests
                    # if it successfully built.
                    if not cancel_event.is_set():
                        built_tests.append(test)
                    else:
                        failed_builds[test.builder.name] = test.full_id
                        test.set_run_complete()

                    # Output test status after joining a thread.
                    if self.verbosity not in (Verbose.QUIET, Verbose.DYNAMIC):
                        notes = self.mb_tracker.get_notes(test.builder)
                        if notes:
                            when, state, msg = notes[-1]
                            when = output.get_relative_timestamp(when)
                            preamble = (self.BUILD_STATUS_PREAMBLE
                                        .format(when=when, test_id=test.full_id,
                                                state_len=STATES.max_length,
                                                state=state))
                            output.fprint(self.outfile, preamble, msg, width=None,
                                          wrap_indent=len(preamble))

            test_threads = [thr for thr in test_threads if thr is not None]

            if not self.ignore_errors and single_cancel_event.is_set():
                for thread in test_threads:
                    thread.join()

                self._abort_builds(local_builds + remote_builds)

            state_counts = self.mb_tracker.state_counts()
            if self.verbosity == Verbose.DYNAMIC:
                # Print a self-clearing one-liner of the counts of the
                # build statuses.
                parts = []
                for state in sorted(state_counts.keys()):
                    parts.append("{}: {}".format(state, state_counts[state]))
                line = ' | '.join(parts)
                output.fprint(self.outfile, line, width=None, end='\r', clear=True)
            elif self.verbosity == Verbose.MAX:
                for test in local_builds:
                    seen = message_counts[test.full_id]
                    msgs = self.mb_tracker.get_notes(test.builder)[seen:]
                    for when, state, msg in msgs:
                        when = output.get_relative_timestamp(when)
                        state = '' if state is None else state
                        preamble = self.BUILD_STATUS_PREAMBLE.format(
                            when=when, test_id=test.id,
                            state_len=STATES.max_length, state=state)

                        output.fprint(self.outfile, preamble, msg, width=None,
                                      wrap_indent=len(preamble))
                    message_counts[test.full_id] += len(msgs)

            time.sleep(self.BUILD_SLEEP_TIME)

        if self.verbosity == Verbose.DYNAMIC:
            # Print a newline after our last status update.
            output.fprint(file=self.outfile, width=None)

        for test in built_tests:
            if not test.build_only:
                self.ready_to_start.append(test)

        for test in remote_builds:
            # If local builds only is set, remote built tests won't even be created.
            self.ready_to_start.append(test)

        self.status.set(S_STATES.SET_BUILD,
                        "Completed build step for {} tests in test set {}."
                        .format(len(built_tests), self.name))


    def kickoff(self) -> Tuple[List[TestRun], List[Job]]:
        """Kickoff all the given tests under this test set.

    :return: The number of jobs kicked off.
    """

        self.status.set(S_STATES.SET_KICKOFF,
                        "Kicking off {} tests in test set {}"
                        .format(len(self.ready_to_start), self.name))

        # Group tests by scheduler
        by_sched = defaultdict(lambda: [])
        for test in self.ready_to_start:
            by_sched[test.scheduler].append(test)

        self.ready_to_start = []

        new_started = []

        start_count = 0
        for sched_name in list(by_sched.keys()):
            scheduler = schedulers.get_plugin(sched_name)
            sched_tests = by_sched[sched_name]

            self.status.set(S_STATES.SET_KICKOFF,
                            "Kicking off {} tests under scheduler {}"
                            .format(len(sched_tests), sched_name))
            sched_errors = scheduler.schedule_tests(self.pav_cfg, sched_tests)

            # We rely on the scheduler to tell us which tests failed.
            err_tests = []
            for err in sched_errors:
                err_tests.extend(err.tests)

            for test in sched_tests:
                if test not in err_tests:
                    new_started.append(test)
                    start_count += 1
                    self.started_tests.append(test)
                else:
                    test.set_run_complete()

            if sched_errors and self.verbosity != Verbose.QUIET:
                test_bullets = '\n'.join('  - {}'.format(test.name) for test in err_tests)
                output.fprint(self.outfile,
                              "There were errors kicking off tests for test set {}.\n"
                              "The following tests were not started:\n{}\n"
                              .format(self.name, test_bullets))

                output.fprint(self.outfile, "Errors:")
                for err in sched_errors:
                    output.fprint(self.outfile, err.pformat(), '\n')

        jobs = dict()
        for test in new_started:
            if test.job is not None:
                jobs[test.job.name] = test.job

        self.status.set(S_STATES.SET_KICKOFF,
                        "Kickoff complete for test set {}. Started {} tests under {} jobs."
                        .format(self.name, start_count, len(jobs)))

        return new_started, list(jobs.values())

    def _abort_builds(self, tests: List[TestRun]):
        """Set the given tests as complete, print user messages about the failure,
        and raise an appropriate error message."""

        for test in tests:
            if (test.status.current().state not in
                    (STATES.BUILD_FAILED, STATES.BUILD_ERROR)):
                test.status.set(
                    STATES.ABORTED,
                    "Run aborted due to failures in other builds.")
            test.set_run_complete()

        if self.verbosity == Verbose.DYNAMIC:
            output.fprint(file=self.outfile, clear=True)
            output.fprint(file=self.outfile)

        msg = [
            "Build error while building tests. Cancelling all builds.\n",
            "Failed builds are placed in <working_dir>/test_runs/"
            "<test_id>/build for the corresponding test run.",
            "Tests with build errors:"
        ]

        test_id = '<id>'
        for tracker in self.mb_tracker.failures():
            test = tracker.test
            if test.full_id.startswith('main'):
                test_id = str(test.id)
            else:
                test_id = test.full_id

            msg.append(
                " - {test} ({id} in test set '{set_name}')"
                .format(test=test.name, id=test_id,
                        set_name=self.name))

        msg.append('')
        msg.append("See test status file (pav cat {id} status) and/or "
                    "the test build log (pav log build {id})"
                    .format(id=test_id))

        msg = '\n  '.join(msg)

        raise TestSetError(msg)

    def cancel(self, reason):
        """Cancel all the tests in the test set."""

        self.status.set(S_STATES.SET_CANCELED,
                        "Test Set {} canceled for this reason: {}"
                        .format(self.name, reason))

        for test in self.tests:
            test.cancel(reason)

        cancel_utils.cancel_jobs(self.pav_cfg, self.tests)

    def force_completion(self):
        """Mark all of the tests as complete. We generally do this after
        an error has been encountered, or if it was only built.
        """

        for test in self.tests:
            test.set_run_complete()

    def mark_completed(self) -> int:
        """Check all tests that we've started for completion, and move them to the
        completed list as appropriate. Returns the number of tests that completed."""

        just_completed = []

        for test in list(self.started_tests):
            if test.complete:
                self.started_tests.remove(test)
                self.completed_tests.append(test)
                just_completed.append(test)

        # All started tests should have a job - Update their status based on that job.
        for test in list(self.started_tests):
            sched = schedulers.get_plugin(test.scheduler)
            status = sched.job_status(self.pav_cfg, test)
            if status.state in (STATES.SCHED_CANCELLED, STATES.SCHED_ERROR):
                # The test will have been marked as complete
                self.started_tests.remove(test)
                self.completed_tests.append(test)
                just_completed.add(test)

        return len(just_completed)

    TEST_WAIT_PERIOD = 0.5

    def wait(self, wait_for_all=False, wait_period: int = TEST_WAIT_PERIOD) -> int:
        """Wait for tests to complete. Returns the number of jobs that completed for this
        call to wait.

        :param wait_for_all: Wait for all started tests to complete before returning.
        :param wait_period: How long to sleep between test status checks.
        :return: The number of completed tests
        """

        # No tests to wait for
        if not self.started_tests:
            return 0

        completed_tests = self.mark_completed()

        while ((wait_for_all and self.started_tests) or
               (not wait_for_all and completed_tests == 0)):
            time.sleep(wait_period)
            completed_tests += self.mark_completed()

        return completed_tests

    @property
    def should_run(self) -> Union[bool, None]:
        """Evaluate whether this set should run at all, and mark it as 'done'
        if not. Returns whether this set should run, or None if that can't be
        determined."""

        if self._should_run is None:

            all_should = True
            all_done = True
            all_passed = True

            for parent in self.parent_sets:
                # If a parent shouldn't run, neither should we.
                if not parent.should_run:
                    all_should = False
                    break

                if self.parents_must_pass:
                    # If the parent should run and has to pass, check that all
                    # tests are done and passing.
                    if parent.done:
                        if not parent.all_passed:
                            all_passed = False
                            break
                    else:
                        all_done = False
                        break

            if not all_should:  # When any parent shouldn't run, this shouldn't either.
                self._should_run = False
            elif self.parents_must_pass:
                if not all_passed:
                    # We care about parents passing, and a parent failed
                    self._should_run = False
                elif all_done:
                    # We care about parents passing, and they all finished and passed.
                    self._should_run = True
                else:
                    # We don't know yet what the answer is.
                    pass
            else:
                # We should run if all parents should and we don't care about parents
                # passing
                self._should_run = True

            if self._should_run is False:
                # We won't have any tests created. This is done
                self.tests = []
                self.started_tests = []

        return self._should_run

    @property
    def done(self) -> bool:
        """Returns True if all the tests in the set are completed."""

        self.mark_completed()


        return (self.all_tests_made
                and not self.ready_to_build
                and not self.ready_to_start
                and not self.started_tests)

    @property
    def all_passed(self) -> bool:
        """Returns true if all tests passed."""

        if not self.done:
            raise RuntimeError("Not all tests have completed, check for completion "
                               "first with TestSet.done().")

        for test in self.completed_tests:
            if test.results['result'] != test.PASS:
                return False

        return True

    def __repr__(self):
        return "<TestSet {} {}>"\
               .format(self.name, ", ".join(self._test_names))
