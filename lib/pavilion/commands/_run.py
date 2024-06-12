"""Given a pre-existing test run, runs the test in the scheduled
environment."""

import sys
import traceback
from pathlib import Path
from typing import List
import threading
import time

from pavilion import result
from pavilion import schedulers
from pavilion import PavConfig
from pavilion.errors import TestRunError, ResultError, TestBuilderError, PavilionError
from pavilion.output import fprint
from pavilion.status_file import STATES
from pavilion.sys_vars import base_classes
from pavilion.test_run import TestRun, mass_status_update
from pavilion.variables import VariableSetManager
from .base_classes import Command

# We need to catch pretty much all exceptions to cleanly report errors.
# pylint: disable=broad-except

class _RunCommand(Command):

    def __init__(self):

        super().__init__(
            '_run',
            'Setup and run a single test, under the assumption we\'re already '
            'in the expected, scheduled environment.')

    def _setup_arguments(self, parser):

        parser.add_argument(
            'test_ids', action='store', nargs='+',
            help='The full id of the test to run.')

    def run(self, pav_cfg, args):
        """Load and run an already prepped test."""

        tests = []
        for test_id in args.test_ids:
            try:
                tests.append(TestRun.load_from_raw_id(pav_cfg, test_id))
            except PavilionError as err:
                fprint(self.outfile, "Error loading test '{}'".format(args.test_id))
                fprint(self.outfile, err.pformat())

        # Filter out cancelled tests
        uncancelled_tests = []
        for test in tests:
            if test.cancelled:
                test.set_run_complete()
            else:
                uncancelled_tests.append(test)
        tests = uncancelled_tests

        tests = [test for test in tests if not test.cancelled]

        finalized_tests = []
        for test in tests:
            try:
                self._finalize_test(pav_cfg, test)
            except PavilionError as err:
                fprint(self.outfile, "Error finalizing test run '{}'".format(test.full_id))
                fprint(self.outfile, err.pformat())
                test.status.set(STATES.RUN_ERROR, "Error finalizing test: {}".format(err))
                test.set_run_complete()
                continue

            # Only add tests that weren't skipped.
            if test.skipped:
                test.status.set(STATES.SKIPPED, "Test skipped based on deferred variables.")
            else:
                finalized_tests.append(test)

        tests = finalized_tests

        # Build any tests that are non-local builds
        # TODO: Do this in parallel
        built_tests = []
        for test in tests:
            try:
                if not test.build_local:
                    test.status.set(STATES.BUILDING, "Test building on an allocation.")
                    if not test.build():
                        test.set_run_complete()
                        fprint(self.outfile, "Test {} build failed.".format(test.full_id))
                        continue
                if not test.build_only:
                    built_tests.append(test)
            except Exception as err:
                test.status.set(
                    STATES.BUILD_ERROR,
                    "Unexpected build error: {}.".format(err))
                test.set_run_complete()
        tests = built_tests

        # Bail if no tests remain
        if not tests:
            fprint(self.outfile, "Of the specified tests that were loaded, none need to "
                                 "(or could) run.")
            return 1

        msg = "Ready to run along with {} other tests.".format(len(tests))
        mass_status_update(tests, STATES.RUN_READY, msg)

        # Run test tests, and make sure they're set as complete regardless of what happens
        try:
            self._run_tests(pav_cfg, tests)
        except Exception as err:
            for test in tests:
                test.status.set(STATES.RUN_ERROR,
                                "Unexpected error in _run command: {}".format(err))
        finally:
            for test in tests:
                test.set_run_complete()

    def _finalize_test(self, pav_cfg: PavConfig, test: TestRun):
        # The scheduler will be the same for all tests

        sched = self._get_sched(test)

        var_man = self._get_var_man(test, sched)
        if var_man.get('sched.errors'):
            test.status.set(
                STATES.RUN_ERROR,
                "Error resolving scheduler variables at run time. "
                "See'pav log kickoff {}' for the full error.".format(test.id))
            raise TestRunError("Error resolving scheduler variables for test {}.\n"
                               .format(test.full_id)
                               + '\n'.join(var_man.get('sched.errors.*')))

        try:
            test.finalize(var_man)
        except Exception as err:
            test.status.set(
                STATES.RUN_ERROR,
                "Unexpected error finalizing test\n{}\n"
                "See 'pav log kickoff {}' for the full error."
                .format(err, test.id))
            raise TestRunError("Could not finalize test '{}'.".format(test.full_id), prior_err=err)


    def _run_tests(self, pav_cfg, tests):
        """Run the given tests according to their allowed concurrency."""

        # Turn this into a stack
        tests.reverse()

        # Track our running tests by full_id
        running_tests : Dict[str, Tuple[threading.Thread, TestRun]] = {}
        while tests or running_tests:
            added_thread = False
            if tests:
                next_test = tests.pop()

                # The maximum number of concurrent tests is the lowest
                # 'concurrent' value from amongst the running tests (plus the
                # one we're about to add).
                next_tests = [test for _, test in running_tests.values()]
                next_tests.append(next_test)
                conc_limit = min([test.concurrent for test in next_tests])
                if len(running_tests) + 1 <= conc_limit:
                    thread = threading.Thread(target=self._run, args=(next_test,))
                    running_tests[next_test.full_id] = (thread, next_test)
                    thread.start()
                    added_thread = True
                else:
                    # The next test puts us over the limit. Wait for tests to die.
                    tests.append(next_test)

            if not added_thread: # Only wait if we didn't add a new thread/test.
                thread_exited = False
                while not thread_exited:
                    for thread, test in list(running_tests.values()):
                        # Remove any completed threads.
                        if not thread.is_alive():
                            thread.join()
                            thread_exited = True
                            test.set_run_complete()
                            del running_tests[test.full_id]

                    if not thread_exited:
                        time.sleep(0.5)

    @staticmethod
    def _get_sched(test):
        """Get the scheduler for the given test.
        :param TestRun test: The test.
        """

        try:
            return schedulers.get_plugin(test.scheduler)
        except Exception:
            test.status.set(STATES.BUILD_ERROR,
                            "Unknown error getting the scheduler. Refer to "
                            "the kickoff log.")
            raise

    @staticmethod
    def _get_var_man(test, sched):
        """Get the variable manager for the given test.

        :param TestRun test: The test run object
        :param sched: The scheduler for this test.
        :rtype VariableSetManager
        """
        # Re-add var sets that may have had deferred variables.
        try:
            var_man = VariableSetManager()
            var_man.add_var_set('sys', base_classes.get_vars(defer=False))
            var_man.add_var_set('sched', sched.get_final_vars(test))
        except Exception:
            test.status.set(STATES.RUN_ERROR,
                            "Unknown error getting pavilion variables at "
                            "run time. See 'pav log kickoff {}' for the "
                            "full error.".format(test.id))
            raise

        return var_man

    def _run(self, test: TestRun):
        """Run an already prepped test in the current environment.
        :return:
        """

        _ = self

        try:
            run_result = test.run()
        except TestRunError as err:
            # An unexpected TestRunError
            test.status.set(STATES.RUN_ERROR, err)
        except TimeoutError:
            # This is expected
            pass
        except Exception:
            # Some other unexpected exception.
            test.status.set(
                STATES.RUN_ERROR,
                "Unknown error while running test. Refer to the kickoff log.")
            return

        try:
            # Make sure the result parsers have reasonable arguments.
            # We check here because the parser code itself will likely assume
            # the args are valid form _check_args, but those might not be
            # check-able before kickoff due to deferred variables.
            try:
                result.check_config(test.config['result_parse'],
                                    test.config['result_evaluate'])
            except ResultError as err:
                test.status.set(
                    STATES.RESULTS_ERROR,
                    "Error checking result parser configs: {}".format(err))
                return

            with test.results_log.open('w') as log_file:
                results = test.gather_results(run_result, log_file=log_file)

        except Exception as err:
            fprint(self.outfile, "Unexpected error gathering results.", err)
            test.status.set(STATES.RESULTS_ERROR,
                            "Unexpected error parsing results: '{}'... (This is a "
                            "bug, you should report it.) "
                            "See 'pav log kickoff {}' for the full error."
                            .format(str(err)[:100], test.id))
            return

        try:
            test.save_results(results)
        except Exception:
            test.status.set(
                STATES.RESULTS_ERROR,
                "Unknown error while saving results. Refer to the kickoff log.")
            return

        try:
            test.status.set(STATES.COMPLETE,
                            "The test completed with result: {}"
                            .format(results.get('result', '<unknown>')))
            # We set the general completion of the test outside of this function, regardless of
            # how it exited.
        except Exception:
            test.status.set(
                STATES.UNKNOWN,
                "Unknown error while setting test completion. Refer to the "
                "kickoff log.")
