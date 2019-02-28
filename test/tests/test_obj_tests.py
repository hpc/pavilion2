import os
import unittest

from pavilion import pav_config
from pavilion import pav_test


class PavTestTests(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        self.pav_cfg.working_dir = '/tmp/{}/pav_test'.format(os.getlogin())

        super().__init__(*args, **kwargs)

    def setUp(self):
        pass

    def test_obj(self):
        """Test pavtest object initialization."""

        # Initializing with a mostly blank config
        config = {
            'name': 'blank_test'
        }

        pav_test.PavTest(self.pav_cfg, config)

        config = {
            'subtest': 'st',
            'name': 'test',
            'build': {
                'modules': ['gcc'],
                'cmds': ['echo "Hello World"'],
            },
            'run': {
                'modules': ['gcc', 'openmpi'],
                'cmds': ['echo "Running dis stuff"'],
                'env': {'BLARG': 'foo'},
            }
        }

        pav_test.PavTest(self.pav_cfg, config)


