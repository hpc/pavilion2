import os
import shutil
import tempfile
import unittest

from pavilion import pav_config
from pavilion import pav_test


class PavTestTests(unittest.TestCase):

    def __init__(self, *args, **kwargs):
        self.pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        self.tmp_dir = tempfile.TemporaryDirectory()

        self.pav_cfg.working_dir = '/tmp/pflarr/pav_test1234' # self.tmp_dir.name

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

        # Make sure we can create a test from a fairly populated config.
        t = pav_test.PavTest(self.pav_cfg, config)

        # Make sure we can recreate the object from id.
        t2 = pav_test.PavTest.from_id(self.pav_cfg, t.id)

        # Make sure the objects are identical
        # This tests the following functions
        #  - from_id
        #  - save_config, load_config
        #  - get_test_path
        for key in set(t.__dict__.keys()).union(t2.__dict__.keys()):
            self.assertEqual(t.__dict__[key], t2.__dict__[key])

