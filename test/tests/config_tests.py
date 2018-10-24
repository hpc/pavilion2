from __future__ import print_function

import unittest

from pavilion import config_format


class TestConfig(unittest.TestCase):
    def test_valid_config(self):
        """Check that a valid config is read correctly."""

        f = open('test_data/config_tests.basics.yaml', 'r')

        data = config_format.TestConfigLoader().load(f)

        self.assertEqual(len(data), 7)
        self.assertEqual(data.inherits_from, 'something_else')
        self.assertEqual(data.scheduler, 'slurm')
        self.assertEqual(data.run.cmds[0], 'true')

        self.assertEqual(len(data.variables), 4)
        self.assertEqual(data.variables.fish, ['halibut'])
        self.assertEqual(data.variables.animal, ['squirrel'])
        self.assertEqual(data.variables.bird, ['eagle', 'mockingbird', 'woodpecker'])
        self.assertEqual(data.variables.horse[0].legs, '4')

