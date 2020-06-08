import io
import os
from pathlib import Path

from pavilion import config
from pavilion.unittest import PavTestCase


class PavConfigTests(PavTestCase):

    def test_blank_cycle(self):
        """Ensure we can both write and read the config template."""

        loader = config.PavilionConfigLoader()

        file = io.StringIO()

        loader.dump(file)
        file.seek(0)
        loader.load(file)

    def test_cycle(self):
        """Make sure we can load the defaults, save them, and reload them."""

        loader = config.PavilionConfigLoader()

        pav_cfg = loader.load_empty()

        file = io.StringIO()

        loader.dump(file, pav_cfg)

        file.seek(0)

        new_cfg = loader.load(file)

        self.assertEqual(pav_cfg, new_cfg)

    def test_ex_path_elem(self):
        """Make sure the ex_path_elem works as expected."""

        elem = config.ExPathElem("test")

        self.assertIsNone(elem.validate(None))
        self.assertEqual(elem.validate("/tmp/$USER/blarg"),
                         Path('/tmp', os.environ['USER'], 'blarg'))
        self.assertEqual(elem.validate("/tmp/${NO_SUCH_VAR}/ok"),
                         Path("/tmp/${NO_SUCH_VAR}/ok"))
