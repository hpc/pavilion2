from pavilion import commands
from pavilion import plugins
from pavilion.unittest import PavTestCase
import argparse
import subprocess

class ExtraPrintsTest(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_for_extra_prints(self):
        """greps for unnecessary dbg_print statements."""

        #cmd = ["""grep -R --exclude={run,show,cancel,set_status,view,log,utils,status}.py -i 'print(' ../lib/pavilion/"""]
        cmd = "grep -R -i -I 'dbg_print' ../lib/pavilion/ --exclude=unittest.py --exclude=utils.py"
        output = subprocess.call(cmd, shell=True)

        self.assertNotEqual(output, 0)
