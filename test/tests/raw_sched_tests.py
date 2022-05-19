import pavilion.schedulers
from pavilion.unittest import PavTestCase


class RawSchedTests(PavTestCase):

    def test_sched_vars(self):
        """Make sure the scheduler variable class works as expected."""

        test = self._quick_test()

        raw_sched = pavilion.schedulers.get_plugin('raw')

        vars = raw_sched.get_initial_vars(test.config['schedule'])

        for key in vars.keys():
            _ = vars[key]
