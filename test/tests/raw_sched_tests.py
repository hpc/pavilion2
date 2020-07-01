from pavilion import plugins
from pavilion import schedulers
from pavilion.test_config import variables
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase
from pavilion.test_config import VariableSetManager
import re


class RawSchedTests(PavTestCase):

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

    def setUp(self):

        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_sched_vars(self):
        """Make sure the scheduler variable class works as expected."""

        test = self._quick_test()

        raw_sched = schedulers.get_plugin('raw')

        vars = raw_sched.get_vars(test.config['raw'])

        for key in vars.keys():
            _ = vars[key]
