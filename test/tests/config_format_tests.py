from __future__ import print_function

from pavilion.test_config import file_format
from pavilion.unittest import PavTestCase
from pavilion.config import PavilionConfigLoader
import tempfile


class TestConfig(PavTestCase):
    def test_valid_test_config(self):
        """Check that a valid config is read correctly."""

        f = (self.TEST_DATA_ROOT/'config_tests.basics.yaml').open()

        data = file_format.TestConfigLoader().load(f)

        self.assertEqual(data.inherits_from, 'something_else')
        self.assertEqual(data.scheduler, 'slurm')
        self.assertEqual(data.run.cmds[0], 'true')

        self.assertEqual(len(data.variables), 4)
        self.assertEqual(data.variables.fish, ['halibut'])
        self.assertEqual(data.variables.animal, ['squirrel'])
        self.assertEqual(data.variables.bird, ['eagle', 'mockingbird',
                                               'woodpecker'])
        self.assertEqual(data.variables.horse[0].legs, '4')

    def test_pav_config_recycle(self):
        """Make sure a config template file is a valid config."""

        tmp_fn = tempfile.mktemp('yaml', dir='/tmp')

        cfg = PavilionConfigLoader().load_empty()
        with open(tmp_fn, 'w') as cfg_file:
            PavilionConfigLoader().dump(cfg_file, cfg)

        with open(tmp_fn) as cfg_file:
            reloaded = PavilionConfigLoader().load(cfg_file)

        self.assertEqual(cfg, reloaded)
