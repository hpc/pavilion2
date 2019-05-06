from pavilion import commands
from pavilion.pavtest import PavTest
from pavilion import schedulers
from pavilion.status_file import STATES
import logging


class _RunCommand(commands.Command):

    def __init__(self):

        super().__init__(
            '_run',
            'Setup and run a single test, under the assumption we\'re already'
            'in the expected, scheduled enviornment.')

    def _setup_arguments(self, parser):

        parser.add_argument(
            'test_id', nargs=1, action='store', type=int,
            help='The id of the test to run.')

    def run(self, pav_cfg, args):
        """Load and run an already prepped test in the current environment."""

        test = PavTest.from_id(pav_cfg, args.test_id)

        sched = schedulers.get_scheduler_plugin(test.scheduler)

        # Optionally wait on other tests running under the same scheduler.
        # This depends on the scheduler and the test configuration.
        lock = sched.lock_concurrency(pav_cfg, test)

        test.run(sched.get_vars(test))

        sched.unlock_concurrency(lock)

        try:
            results = test.gather_results(pav_cfg)
        except (Exception) as err:
            self.logger.error("Unexpected error gathering results: {}"
                              .format(err))

        results_log = logging.getLogger('results')

        test.status.set(STATES.COMPLETE)

