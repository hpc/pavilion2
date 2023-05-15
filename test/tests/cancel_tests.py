import time

from pavilion import cancel
from pavilion import schedulers
from pavilion import unittest
from pavilion.status_file import STATES


class CancelTests(unittest.PavTestCase):
    """Tests on job/test cancellation."""

    def test_cancel_jobs(self):
        """Test job cancellation function."""

        test_cfg = self._quick_test_cfg()
        test_cfg['run']['cmds'] = ['sleep 5']
        test_cfg['scheduler'] = 'dummy'
        test_cfg['schedule'] = {'nodes': 'all'} 
        test1 = self._quick_test(test_cfg, finalize=False)
        test2 = self._quick_test(test_cfg, finalize=False)

        sched = schedulers.get_plugin(test1.scheduler)

        sched.schedule_tests(self.pav_cfg, [test1, test2])
        time.sleep(0.5)

        test1.cancel("For fun")

        # Wait till we know test2 is running
        while not test1.complete:
            time.sleep(0.1)

        while not test2.status.has_state(STATES.RUNNING):
            time.sleep(0.1)

        jobs = cancel_utils.cancel_jobs(self.pav_cfg, [test1, test2])
        self.assertEqual(test2.status.current().state, STATES.RUNNING)
        self.assertTrue(test1.cancelled)
        self.assertFalse(jobs[0]['success'])

        test2.cancel('for other reasons')
        jobs = cancel_utils.cancel_jobs(self.pav_cfg, [test1, test2])
        self.assertTrue(test2.cancelled)
        self.assertTrue(test1.cancelled)
        self.assertTrue(jobs[0]['success'])

        # Big note - the dummy scheduler doesn't actually know how to cancel jobs.
        #   That's ok though, since it will tell cancel_job what it wants to here.
