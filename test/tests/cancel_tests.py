import time

from pavilion import cancel_utils
from pavilion import schedulers
from pavilion import unittest
from pavilion.status_file import STATES
from pavilion.timing import wait


class CancelTests(unittest.PavTestCase):
     """Tests on job/test cancellation."""

     def __init__(self, *args, **kwargs):
          super().__init__(*args, **kwargs)

          self.link_files("plugins/schedulers/dummy.*")

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
          try:
               wait(lambda: test1.complete, interval=0.2, timeout=self.testrun_wait_timeout)
          except TimeoutError:
               self.fail(f"Timed out waiting for test to complete after {self.testrun_wait_timeout} "
                         "seconds.")

          try:
               wait(lambda: test2.status.has_state(STATES.RUNNING), interval=0.2, timeout=self.testrun_start_timeout)
          except TimeoutError:
               self.fail(f"Timed out waiting for test to begin running after "
                         f"{self.testrun_start_timeout} seconds.")

          jobs = cancel_utils.cancel_jobs(self.pav_cfg, [test1, test2])
          self.assertEqual(test2.status.current().state, STATES.RUNNING, msg=f"Test {test2.id} does not have state 'RUNNING'.")
          self.assertTrue(test1.cancelled)
          self.assertFalse(jobs[0]['success'])

          test2.cancel('for other reasons')
          jobs = cancel_utils.cancel_jobs(self.pav_cfg, [test1, test2])
          self.assertTrue(test2.cancelled)
          self.assertTrue(test1.cancelled)
          self.assertTrue(jobs[0]['success'])

          # Big note - the dummy scheduler doesn't actually know how to cancel jobs.
          #   That's ok though, since it will tell cancel_job what it wants to here.
