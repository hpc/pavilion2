import logging
import sys

from pavilion import commands
from pavilion import result_parsers
from pavilion import schedulers
from pavilion import system_variables
from pavilion import utils
from pavilion.test_run import TestRun, TestRunError
from pavilion.status_file import STATES


class _RunCommand(commands.Command):

    def __init__(self):

        super().__init__(
            '_run',
            'Setup and run a single test, under the assumption we\'re already'
            'in the expected, scheduled environment.')

    def _setup_arguments(self, parser):

        parser.add_argument(
            'test_id', action='store', type=int,
            help='The id of the test to run.')

    def run(self, pav_cfg, args):
        """Load and run an already prepped test in the current environment.
        """

        try:
            test = TestRun.load(pav_cfg, args.test_id)
        except TestRunError as err:
            self.logger.error("Error loading test '%s': %s",
                              args.test_id, err)
            raise

        try:
            if test.config['build']['on_nodes'] in ['true', 'True']:
                if not test.build():
                    self.logger.warning(
                        "Test {t.id} failed to build:"
                    )
        except Exception:
            test.status.set(STATES.BUILD_ERROR,
                            "Unknown build error. Refer to the kickoff log.")
            raise

        try:
            sched = schedulers.get_scheduler_plugin(test.scheduler)
        except Exception:
            test.status.set(STATES.BUILD_ERROR,
                            "Unknown error getting the scheduler. Refer to "
                            "the kickoff log.")
            raise

        # Optionally wait on other tests running under the same scheduler.
        # This depends on the scheduler and the test configuration.
        lock = sched.lock_concurrency(pav_cfg, test)

        try:
            run_result = test.run(sched.get_vars(test),
                                  system_variables.get_vars(defer=False))
        except TestRunError as err:
            test.status.set(STATES.RUN_ERROR, err)
            test.set_run_complete()
            return 1
        except Exception:
            test.status.set(
                STATES.RUN_ERROR,
                "Unknown error while running test. Refer to the kickoff log.")
            raise
        finally:
            sched.unlock_concurrency(lock)

        # The test.run() method should have already logged the error and
        # set an appropriate status.
        if run_result in (STATES.RUN_ERROR, STATES.RUN_TIMEOUT):
            return 1

        try:
            rp_errors = []
            # Make sure the result parsers have reasonable arguments.
            # We check here because the parser code itself will likely assume
            # the args are valid form _check_args, but those might not be
            # checkable before kickoff due to deferred variables.
            try:
                result_parsers.check_args(test.config['results'])
            except TestRunError as err:
                rp_errors.append(str(err))

            if rp_errors:
                for msg in rp_errors:
                    test.status.set(STATES.RESULTS_ERROR, msg)
                test.set_run_complete()
                return 1

            results = test.gather_results(run_result)
        except result_parsers.ResultParserError as err:
            self.logger.error("Unexpected error gathering results: %s", err)
            test.status.set(STATES.RESULTS_ERROR,
                            "Error parsing results: {}".format(err))
            test.set_run_complete()
            return 1

        try:
            test.save_results(results)

            result_logger = logging.getLogger('results')
            result_logger.info(utils.json_dumps(results))
        except Exception:
            test.status.set(
                STATES.RESULTS_ERROR,
                "Unknown error while saving results. Refer to the kickoff log.")
            raise

        try:
            test.status.set(STATES.COMPLETE,
                            "The test completed with result: {}"
                            .format(results.get('result', '<unknown>')))
            test.set_run_complete()
        except Exception:
            test.status.set(
                STATES.UNKNOWN,
                "Unknown error while setting test completion. Refer to the "
                "kickoff log.")
            raise
