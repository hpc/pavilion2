from pavilion import plugins
from pavilion import unittest
from pavilion import schedulers
from pavilion import cancel
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
import time


class AutoexitTests(unittest.PavTestCase):
    """Test the autoexit config option."""

    def setUp(self):
        """This has to run before any command plugins are loaded."""
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self) -> None:
        """Reset all plugins."""
        plugins._reset_plugins()

    def test_autoexit(self):
        """Test the autoexit config option."""

        cfg_true = self._quick_test_cfg()
        cfg_true['run'] = {'cmds': ['false']}
        
        #cfg_false = self._quick_test_cfg()
        #cfg_false['build'] = {'autoexit': 'False'}
        #cfg_false['run'] = {'cmds': 'False'}

        test = self._quick_test(cfg=cfg_true)
        test.run()

        results = test.gather_results(0)
        print(results)

        self.assertEqual(test.results['result'], TestRun.FAIL)    