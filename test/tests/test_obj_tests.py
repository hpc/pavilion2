import os
import shutil
import tempfile
import unittest

from pavilion import pav_config
from pavilion import pav_test


class PavTestTests(unittest.TestCase):

    TEST_DATA_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    TEST_DATA_ROOT = os.path.join(TEST_DATA_ROOT, 'test_data')

    def __init__(self, *args, **kwargs):

        self.pav_cfg = pav_config.PavilionConfigLoader().load_empty()

        self.pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir')]

        self.tmp_dir = tempfile.TemporaryDirectory()

        self.pav_cfg.working_dir = '/tmp/pflarr/pav_test' # self.tmp_dir.name

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
        #  - write_tmpl
        for key in set(t.__dict__.keys()).union(t2.__dict__.keys()):
            self.assertEqual(t.__dict__[key], t2.__dict__[key])

    def test_setup_build_dir(self):
        """Make sure we can correctly handle all of the various archive formats."""

        base_config = {
            'name': 'test',
            'build': {
                'modules': ['gcc'],
            }
        }

        archives = [
            'src.tar.gz',
            'src.xz',
            # A bz2 archive
            'src.extensions_dont_matter',
            'src.zip',
            # These archives don't have a containing directory.
            'no_encaps.tgz',
            'no_encaps.zip',
        ]

        test_archives = os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir', 'test_src')
        original_tree = os.path.join(test_archives, 'src')

        for archive in archives:
            config = base_config.copy()
            config['build']['source_location'] = archive

            test = pav_test.PavTest(self.pav_cfg, config=config)

            if os.path.exists(test.build_origin):
                shutil.rmtree(test.build_origin)

            test._setup_build_dir(test.build_origin)

            # Make sure the extracted archive is identical to the original
            # (Though the containing directory will have a different name)
            self._cmp_tree(test.build_origin, original_tree)

        # Check directory copying
        config = base_config.copy()
        config['build']['source_location'] = 'src'
        test = pav_test.PavTest(self.pav_cfg, config=config)

        if os.path.exists(test.build_origin):
            shutil.rmtree(test.build_origin)

        test._setup_build_dir(test.build_origin)
        self._cmp_tree(test.build_origin, original_tree)

        # Test single compressed files.
        files = [
            'binfile.gz',
            'binfile.bz2',
            'binfile.xz',
        ]

        for file in files:
            config = base_config.copy()
            config['build']['source_location'] = file
            test = pav_test.PavTest(self.pav_cfg, config=config)

            if os.path.exists(test.build_origin):
                shutil.rmtree(test.build_origin)

            test._setup_build_dir(test.build_origin)
            with open(os.path.join(test.build_origin, 'binfile'), 'rb') as build_file,\
                 open(os.path.join(original_tree, 'binfile'), 'rb') as orig_file:
                self.assertEqual(build_file.read(), orig_file.read(),
                                 "Extracted files don't match.")

    def _cmp_tree(self, a, b):
        a_walk = list(os.walk(a))
        b_walk = list(os.walk(b))

        # Make sure these are in the same order.
        a_walk.sort()
        b_walk.sort()

        while a_walk and b_walk:
            a_dir, a_dirs, a_files = a_walk.pop(0)
            b_dir, b_dirs, b_files = b_walk.pop(0)

            self.assertEqual(sorted(a_dirs), sorted(b_dirs),
                             "Extracted archive subdir mismatch for '{}' {} != {}"
                             .format(a, a_dirs, b_dirs))

            # Make sure these are in the same order.
            a_files.sort()
            b_files.sort()

            self.assertEqual(a_files, b_files, "Extracted archive file list mismatch. "
                                               "{} != {}".format(a_files, b_files))

            for file in a_files:
                # The file names have are been verified as the same.
                a_path = os.path.join(a_dir, file)
                b_path = os.path.join(b_dir, file)

                # We know the file exists in a, does it in b?
                self.assert_(os.path.exists(b_path),
                             "File missing from archive b '{}'".format(b_path))

                with open(a_path, 'rb') as a_file, open(b_path, 'rb') as b_file:
                    self.assertEqual(a_file.read(), b_file.read(),
                                     "File contents mismatch for {} and {}."
                                     .format(a_path, b_path))

        self.assert_(not a_walk and not b_walk,
                     "Left over directory contents in a or b: {}, {}".format(a_walk, b_walk))

