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
        """greps for unnecessary print statements."""
        #self.assertNotEqual(1,1)

        cmd = ["""grep -R --exclude={run,show,cancel,set_status,view,log,utils,status}.py -i 'print(' ../lib/pavilion/"""]
        output = subprocess.call(cmd, shell=True)

        self.assertNotEqual(output, 0)
