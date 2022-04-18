"""Given a pre-existing test run, runs the test in the scheduled
environment."""

import traceback
from pathlib import Path

from pavilion.output import fprint
from pavilion import result
from pavilion import schedulers
from pavilion.status_file import STATES
from pavilion.sys_vars import base_classes
from pavilion.variables import VariableSetManager
from pavilion.resolver import TestConfigResolver
from pavilion.test_run import TestRun
from pavilion.exceptions import TestRunError
from .base_classes import Command


class _RunCommand(Command):

    def __init__(self):

        super().__init__(
            '_run',
            'Setup and run a single test, under the assumption we\'re already'
            'in the expected, scheduled environment.')

    def _setup_arguments(self, parser):

        parser.add_argument(
            'working_dir', action='store', type=Path,
            help='Working directory in which this test run resides.'
        )

        parser.add_argument(
            'test_id', action='store', type=int,
            help='The id of the test to run.')

    def run(self, pav_cfg, args):
        """Load and run an already prepped test."""

        try:
            test = TestRun.load(pav_cfg, working_dir=args.working_dir,
                                test_id=args.test_id)
        except TestRunError as err:
            fprint(sys.stdout, "Error loading test '{}': {}".format(args.test_id, err))
            raise

        try:
            sched = self._get_sched(test)

            var_man = self._get_var_man(test, sched)
            if var_man.get('sched.errors'):
                test.status.set(
                    STATES.RUN_ERROR,
                    "Error resolving scheduler variables at run time. "
                    "See'pav log kickoff {}' for the full error.".format(test.id))
                fprint(sys.stdout, "Error resolving scheduler variables at run time. Got "
                                   "the following:")
                for error in var_man.get('sched.errors.*'):
                    fprint(sys.stdout, error)

            try:
                TestConfigResolver.finalize(test, var_man)
            except Exception as err:
                test.status.set(
                    STATES.RUN_ERROR,
                    "Unexpected error finalizing test\n{}\n"
                    "See 'pav log kickoff {}' for the full error."
                    .format(err.args[0], test.id))
                raise

            if test.skipped:
                # The test is skipped, so it shouldn't build or run.
                return 0

            try:
                if not test.build_local:
                    if not test.build():
                        fprint(sys.stdout, "Test {} failed to build.".format(test.full_id))

            except Exception:
                test.status.set(
                    STATES.BUILD_ERROR,
                    "Unknown build error. Refer to the kickoff log.")
                raise

            if not test.build_only:
                return self._run(test)
        finally:
            test.set_run_complete()

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
                            "run time. See'pav log kickoff {}' for the "
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
            test.status.set(STATES.RUN_ERROR, err)
            return 1
        except TimeoutError:
            return 1
        except Exception:
            test.status.set(
                STATES.RUN_ERROR,
                "Unknown error while running test. Refer to the kickoff log.")
            raise

        if test.cancelled:
            # Skip the result parsing step if the test was cancelled.
            return

        try:
            # Make sure the result parsers have reasonable arguments.
            # We check here because the parser code itself will likely assume
            # the args are valid form _check_args, but those might not be
            # check-able before kickoff due to deferred variables.
            try:
                result.check_config(test.config['result_parse'],
                                    test.config['result_evaluate'])
            except result.ResultError as err:
                test.status.set(
                    STATES.RESULTS_ERROR,
                    "Error checking result parser configs: {}"
                    .format(err.args[0]))
                return 1

            with test.results_log.open('w') as log_file:
                results = test.gather_results(run_result, log_file=log_file)

        except Exception as err:
            fprint(sys.stdout, "Unexpected error gathering results: \n{}", traceback.format_exc())
            test.status.set(STATES.RESULTS_ERROR,
                            "Unexpected error parsing results: {}. (This is a "
                            "bug, you should report it.)"
                            "See 'pav log kickoff {}' for the full error."
                            .format(err, test.id))
            raise

        try:
            test.save_results(results)
        except Exception:
            test.status.set(
                STATES.RESULTS_ERROR,
                "Unknown error while saving results. Refer to the kickoff log.")
            raise

        try:
            test.status.set(STATES.COMPLETE,
                            "The test completed with result: {}"
                            .format(results.get('result', '<unknown>')))
        except Exception:
            test.status.set(
                STATES.UNKNOWN,
                "Unknown error while setting test completion. Refer to the "
                "kickoff log.")
            raise
