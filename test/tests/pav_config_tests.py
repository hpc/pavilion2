from pavilion.unittest import PavTestCase
from pavilion import config
import io


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
