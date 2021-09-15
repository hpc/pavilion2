"""Test sets translate the specifications of which tests to run (with which options),
into a set of ready to run tests. They are ephemeral, and are not tracked between
Pavilion runs."""

import logging
import threading
import time
from collections import defaultdict
from io import StringIO
from typing import List, Dict, TextIO, Union, Set

from pavilion import test_config, output, result, schedulers
from pavilion.build_tracker import MultiBuildTracker
from pavilion.status_file import STATES
from pavilion.test_config import TestConfigError
from pavilion.utils import str_bool
from pavilion.test_run import TestRun, TestRunError


class TestSetError(RuntimeError):
    """For when creating a test set goes wrong."""


class TestSet:
    """A set of tests given a set of test configuration options. In general,
    setting up a test set involves the following steps:

    - Init: test_set = TestSet()
    - Test Construction: test_set.make_tests()
    - Test Building: test_set.build_local()
    - Kickoff: test_set.kickoff()
    """

    LOGGER_FMT = 'series({})'

    # need info like
    # modes, only/not_ifs, next, prev
    def __init__(self,
                 pav_cfg,
                 name: str,
                 test_names: List[str],
                 modes: List[str] = None,
                 host: str = None,
                 only_if: Dict[str, List[str]] = None,
                 not_if: Dict[str, List[str]] = None,
                 overrides: List = None,
                 parents_must_pass: bool = False):
        """Initialize the tests given these options, creating TestRun objects.

        :param pav_cfg: The Pavilion configuration.
        :param name: The name of this test set.
        :param test_names: A list of test/suite names.
        :param modes: Modes to apply to all tests.
        :param host: Host configuration name to run under.
        :param only_if: Global 'only_if' conditions.
        :param not_if: Global 'not_if' conditions.
        :param overrides: Configuration overrides.
        :param parents_must_pass: Parent test sets must pass for this test set to run.
        """

        self.name = name

        self.modes = modes or []
        self.host = host
        self.only_if = only_if or {}
        self.not_if = not_if or {}
        self.pav_cfg = pav_cfg
        self.overrides = overrides or []

        self.parent_sets = set()  # type: Set[TestSet]
        self.child_sets = set()  # type: Set[TestSet]
        self.parents_must_pass = parents_must_pass

        self.logger = logging.getLogger(name)

        self.tests = None  # type: Union[List[TestRun], None]
        self.built_tests = None
        self.ready_to_start_tests = None  # type: Union[Dict[str, List[TestRun]], None]
        self.started_tests = None  # type: Union[List[TestRun], None]
        self.completed_tests = None  # type: Union[List[TestRun], None]

        self._should_run = None
        self._test_names = test_names
        self.mb_tracker = MultiBuildTracker()

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
                modes=self.modes,
                host=self.host,
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

    def make(self, build_only=False, rebuild=False, local_builds_only=False,
             outfile: TextIO = StringIO()):
        """Resolve the given tests names and options into actual tests, and print
        the test creation status."""

        if self.tests is not None:
            self.cancel("System Error")
            raise RuntimeError("Already created the tests for TestSet '{}'"
                               .format(self.name))

        global_conditions = {
            'only_if': self.only_if,
            'not_if': self.not_if
        }

        cfg_resolver = test_config.TestConfigResolver(self.pav_cfg)

        try:
            test_configs = cfg_resolver.load(
                self._test_names,
                self.host,
                self.modes,
                self.overrides,
                conditions=global_conditions,
                outfile=outfile,
            )
        except TestConfigError as err:
            raise TestSetError(
                "Error loading test configs for test set '{}': {}"
                .format(self.name, err.args[0]))

        progress = 0
        tot_tests = len(test_configs)
        self.tests = []

        for ptest in test_configs:
            if local_builds_only:
                # Don't create test objects for tests that would build remotely.
                if str_bool(ptest.config.get('build', {}).get('on_nodes', 'False')):
                    # TODO: Log that the test was not created.
                    continue

            try:
                test_run = TestRun(pav_cfg=self.pav_cfg, config=ptest.config,
                                   var_man=ptest.var_man, rebuild=rebuild,
                                   build_only=build_only)
                test_run.save(self.mb_tracker)
                self.tests.append(test_run)
                progress += 1.0 / tot_tests
                output.fprint("Creating Test Runs: {:.0%}".format(progress),
                              file=outfile, end='\r')
            except (TestRunError, TestConfigError) as err:
                self.cancel("Error creating other tests in test set '{}'"
                            .format(self.name))
                raise TestSetError("Error creating tests in test set '{}': {}"
                                   .format(self.name, err.args[0]))

        output.fprint('', file=outfile)

        # make sure result parsers are ok
        self.check_result_format(self.tests)

    BUILD_STATUS_PREAMBLE = '{when:20s} {test_id:6} {state:{state_len}s}'
    BUILD_SLEEP_TIME = 0.1

    def build(self, verbosity=0, outfile: TextIO = StringIO()):
        """Build all the tests in this Test Set in parallel. This handles user output
        during the build process.

        :param verbosity: The build verbosity.
            0 - one line summary
            1 - rolling summary
            2 - verbose
        :param outfile: Where to forward user output
        :return:
        """

        if self.tests is None:
            raise RuntimeError("You must run TestSet.make() on the test set before"
                               "it can be built.")

        output.fprint("Building {} tests for test set {}."
                      .format(len(self.tests), self.name), file=outfile)

        outfile = outfile or StringIO()

        local_builds = list(filter(
            lambda t: t.build_local and not t.skipped, self.tests))
        remote_builds = list(filter(
            lambda t: not t.build_local and not t.skipped, self.tests))
        test_threads = []  # type: List[Union[threading.Thread, None]]

        cancel_event = threading.Event()

        # Generate new build names for each test that is rebuilding.
        # We do this here, even for non_local builds, because otherwise the
        # non-local builds can't tell what was built fresh either on a
        # front-end or by other tests rebuilding on nodes.
        for test in local_builds + remote_builds:
            if test.rebuild and test.builder.exists():
                test.builder.deprecate()
                test.builder.rename_build()
                test.build_name = test.builder.name
                test.save_attributes()

        # We don't want to start threads that are just going to wait on a lock,
        # so we'll rearrange the builds so that the unique build names go first.
        # We'll use this as a stack, so tests that should build first go at
        # the end of the list.
        build_order = []
        # If we've seen a build name, the build can go later.
        seen_build_names = set()

        for test in local_builds:
            # Don't try to build tests that are skipped

            if test.builder.name not in seen_build_names:
                build_order.append(test)
                seen_build_names.add(test.builder.name)
            else:
                build_order.insert(0, test)

        # Keep track of what the last message printed per build was.
        # This is for double build verbosity.
        message_counts = {test.full_id: 0 for test in local_builds}

        # Used to track which threads are for which tests.
        test_by_threads = {}

        if verbosity > 0:
            output.fprint(
                self.BUILD_STATUS_PREAMBLE.format(
                    when='When', test_id='TestID',
                    state_len=STATES.max_length, state='State'),
                'Message', file=outfile, width=None)

        builds_running = 0
        # Run and track <max_threads> build threads, giving output according
        # to the verbosity level. As threads finish, new ones are started until
        # either all builds complete or a build fails, in which case all tests
        # are aborted.
        while build_order or test_threads:
            # Start a new thread if we haven't hit our limit.
            if build_order and builds_running < self.pav_cfg.build_threads:
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
                    del test_by_threads[thread]

                    # Only output test status after joining a thread.
                    if verbosity == 1:
                        notes = self.mb_tracker.get_notes(test.builder)
                        when, state, msg = notes[-1]
                        when = output.get_relative_timestamp(when)
                        preamble = (self.BUILD_STATUS_PREAMBLE
                                    .format(when=when, test_id=test.full_id,
                                            state_len=STATES.max_length,
                                            state=state))
                        output.fprint(preamble, msg, wrap_indent=len(preamble),
                                      file=outfile, width=None)

            test_threads = [thr for thr in test_threads if thr is not None]

            if cancel_event.is_set():
                for thread in test_threads:
                    thread.join()

                for test in self.tests:
                    if (test.status.current().state not in
                            (STATES.BUILD_FAILED, STATES.BUILD_ERROR)):
                        test.status.set(
                            STATES.ABORTED,
                            "Run aborted due to failures in other builds.")
                    test.set_run_complete()

                output.fprint(
                    color=output.RED, file=outfile, clear=True)
                output.fprint(
                    color=output.CYAN, file=outfile)

                msg = [
                    "Build error while building tests. Cancelling all builds.",
                    "Failed builds are placed in <working_dir>/test_runs/"
                    "<test_id>/build for the corresponding test run.",
                    "Errors:"
                ]

                failed_test_ids = []
                for failed_build in self.mb_tracker.failures():
                    failed_test_ids.append(str(failed_build.test.id))

                    msg.append(
                        "Build error for test {f.test.name} (#{id}) in "
                        "test set '{set_name}'."
                        "See test status file (pav cat {id} status) and/or "
                        "the test build log (pav log build {id})"
                        .format(f=failed_build, id=failed_build.test.id,
                                set_name=self.name))

                raise TestSetError(msg)

            state_counts = self.mb_tracker.state_counts()
            if verbosity == 0:
                # Print a self-clearing one-liner of the counts of the
                # build statuses.
                parts = []
                for state in sorted(state_counts.keys()):
                    parts.append("{}: {}".format(state, state_counts[state]))
                line = ' | '.join(parts)
                output.fprint(line, end='\r', file=outfile, width=None,
                              clear=True)
            elif verbosity > 1:
                for test in local_builds:
                    seen = message_counts[test.full_id]
                    msgs = self.mb_tracker.messages[test.builder][seen:]
                    for when, state, msg in msgs:
                        when = output.get_relative_timestamp(when)
                        state = '' if state is None else state
                        preamble = self.BUILD_STATUS_PREAMBLE.format(
                            when=when, test_id=test.id,
                            state_len=STATES.max_length, state=state)

                        output.fprint(preamble, msg, wrap_indent=len(preamble),
                                      file=outfile, width=None)
                    message_counts[test.full_id] += len(msgs)

            time.sleep(self.BUILD_SLEEP_TIME)

        if verbosity == 0:
            # Print a newline after our last status update.
            output.fprint(width=None, file=outfile)

        self.built_tests = local_builds
        self.ready_to_start_tests = defaultdict(lambda: [])
        for test in self.tests:
            if not (test.build_only and test.build_local) and not test.skipped:
                self.ready_to_start_tests[test.scheduler].append(test)

    def kickoff(self, start_max: int = None) -> int:
        """Kickoff the tests in this set.

    :param start_max: The maximum number of tests to start.
    :return: The number of tests kicked off.
    """

        if self.tests is None:
            self.cancel("System error.")
            raise RuntimeError("You must run TestRun.make() before kicking off tests.")
        elif self.built_tests is None:
            self.cancel("System error.")
            raise RuntimeError("You must run TestRun.build() before kicking off tests.")

        ready_count = sum(map(len, self.ready_to_start_tests.values()))
        if not ready_count:
            return 0

        ready_tests = self.ready_to_start_tests

        self.started_tests = []
        self.completed_tests = []

        if start_max is None:
            start_max = ready_count

        start_count = 0
        while start_max > 0 and ready_tests.keys():
            for sched_name in list(ready_tests.keys()):
                scheduler = schedulers.get_plugin(sched_name)
                tests = []
                while len(tests) < start_max and ready_tests[sched_name]:
                    tests.append(ready_tests[sched_name].pop(0))

                if not ready_tests[sched_name]:
                    del ready_tests[sched_name]

                start_max -= len(tests)
                start_count += len(tests)

                try:
                    scheduler.schedule_tests(self.pav_cfg, tests)
                except schedulers.SchedulerPluginError as err:
                    self.cancel(
                        "Error scheduling tests (not necessarily this one): {}"
                        .format(err.args[0]))
                    raise TestSetError(
                        "Error starting tests in test set '{}': {}"
                        .format(self.name, err.args[0]))

                self.started_tests.extend(tests)

        return start_count

    def cancel(self, reason):
        """Cancel all the tests in the test set."""

        for test in self.tests:
            scheduler = schedulers.get_plugin(test.scheduler)
            scheduler.cancel_job(test)
            test.status.set(test.status.STATES.ABORTED, reason)

    @staticmethod
    def check_result_format(tests: List[TestRun]):
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
            msg = ["Result Parser configuration had errors:"]
            for test, error in rp_errors:
                msg.append("{} - {}".format(test.name, error))

            raise TestSetError(msg)

    def force_completion(self):
        """Mark all of the tests as complete. We generally do this after
        an error has been encountered, or if it was only built.
        """

        for test in self.tests:
            test.set_run_complete()

    def mark_completed(self) -> int:
        """Check all tests that we've started for completion, and move them to the
        completed list as appropriate. Returns the number of tests marked as
        complete."""

        marked = 0

        if self.started_tests is None:
            return 0

        for test in list(self.started_tests):
            if test.complete:
                self.started_tests.remove(test)
                self.completed_tests.append(test)
                marked += 1

        return marked

    TEST_WAIT_PERIOD = 0.5

    def wait(self, wait_for_all=False, wait_period: int = TEST_WAIT_PERIOD) -> int:
        """Wait for tests to complete. Returns the number of tests that completed
        when one or more tests have completed.

        :param wait_for_all: Wait for all started tests to complete before returning.
        :param wait_period: How long to sleep between test status checks.
        :return: The number of tests that completed.
        """

        marked = self.mark_completed()

        # No tests to wait for
        if not self.started_tests:
            return 0

        while ((wait_for_all and self.started_tests) or
               (not wait_for_all and marked)):
            time.sleep(wait_period)
            marked += self.mark_completed()

        return marked

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
                self.ready_to_start_tests = {}
                self.started_tests = []

        return self._should_run

    @property
    def done(self) -> bool:
        """Returns True if all the tests in the set are completed."""

        self.mark_completed()

        return (self.ready_to_start_tests is not None and  # We had tests to start
                (not self.ready_to_start_tests) and  # They were all started
                (not self.started_tests))  # They all completed.

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
