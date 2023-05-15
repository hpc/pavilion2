from pavilion import plugins
from pavilion import unittest
from pavilion import schedulers
from pavilion import cancel
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
import time


class AutoexitTests(unittest.PavTestCase):
    """Test the autoexit config option."""

    def test_autoexit(self):
        """Test the autoexit config option."""

        cfg_run_yes = self._quick_test_cfg()
        cfg_run_yes['run'] = {'cmds': ['false', 'true']}
        test = self._quick_test(cfg=cfg_run_yes)
        testreturn = test.run()
        self.assertNotEqual(testreturn, 0)

        cfg_run_no = self._quick_test_cfg()
        cfg_run_no['run'] = {'cmds': ['false', 'true'], 'autoexit': 'False'}
        test = self._quick_test(cfg=cfg_run_no)
        testreturn = test.run()
        self.assertEqual(testreturn, 0)
