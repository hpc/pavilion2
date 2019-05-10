from pavilion import commands
from pavilion import schedulers
from pavilion import system_variables
from pavilion import utils
from pavilion.pavtest import PavTest, PavTestError
from pavilion.status_file import STATES
import logging


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
        """Load and run an already prepped test in the current environment."""

        try:
            test = PavTest.load(pav_cfg, args.test_id)
        except PavTestError as err:
            self.logger.error("Error loading test '{}': {}"
                              .format(args.test_id, err))
            raise

        if test.config['build']['on_nodes'] in ['true', 'True']:
            if not test.build():
                self.logger.warning(
                    "Test {t.id} failed to build:"
                )

        sched = schedulers.get_scheduler_plugin(test.scheduler)

        # Optionally wait on other tests running under the same scheduler.
        # This depends on the scheduler and the test configuration.
        lock = sched.lock_concurrency(pav_cfg, test)

        try:
            result = test.run(sched.get_vars(test),
                              system_variables.get_vars(defer=False))
        except PavTestError as err:
            test.status.set(STATES.RUN_ERROR, err)
            test.set_run_complete()
            return
        finally:
            sched.unlock_concurrency(lock)

        try:
            results = test.gather_results(result)
        except Exception as err:
            self.logger.error("Unexpected error gathering results: {}"
                              .format(err))
            test.status.set(STATES.RESULTS_ERROR,
                            "Error parsing results: {}".format(err))
            test.set_run_complete()
            return

        result_logger = logging.getLogger('results')
        result_logger.info(utils.json_dumps(results))

        test.status.set(STATES.COMPLETE, "Test completed successfully.")
        test.set_run_complete()
