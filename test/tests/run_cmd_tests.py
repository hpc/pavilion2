import os

from pavilion import plugins
from pavilion import commands
from pavilion.unittest import PavTestCase


class PavTestTests(PavTestCase):

    def setUp(self):
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):
        plugins._reset_plugins()

    def test_get_tests(self):

        self._cprint(commands._COMMANDS)

        run_cmd = commands.get_command('run')

        run_cmd._get_tests(self.pav_cfg,
                           'this',
                           [],
                           ['hello_world'],
                           [],
                           {})


