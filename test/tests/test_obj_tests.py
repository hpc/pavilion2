import os
import shutil
import tempfile
import unittest

from pavilion import pav_config
from pavilion import pav_test
from pavilion import variables


class PavTestTests(unittest.TestCase):

    TEST_DATA_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
    TEST_DATA_ROOT = os.path.join(TEST_DATA_ROOT, 'test_data')

    PAV_CONFIG_PATH = os.path.join(TEST_DATA_ROOT, 'pav_config_dir', 'pavilion.yaml')

    TEST_URL = 'https://github.com/lanl/Pavilion/archive/2.0.zip'

    def __init__(self, *args, **kwargs):

        with open(self.PAV_CONFIG_PATH) as cfg_file:
            self.pav_cfg = pav_config.PavilionConfigLoader().load(cfg_file)

        self.pav_cfg.config_dirs = [os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir')]

        self.tmp_dir = tempfile.TemporaryDirectory()

        self.pav_cfg.working_dir = '/tmp/pflarr/pav_test' # self.tmp_dir.name

        # Create the basic directories in the working directory
        for path in [self.pav_cfg.working_dir,
                     os.path.join(self.pav_cfg.working_dir, 'builds'),
                     os.path.join(self.pav_cfg.working_dir, 'tests'),
                     os.path.join(self.pav_cfg.working_dir, 'downloads')]:
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)

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

        # Check that decompression and setup works for all accepted types.
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
            self._cmp_files(os.path.join(test.build_origin, 'binfile'),
                            os.path.join(original_tree, 'binfile'))

        # Make sure extra files are getting copied over.
        config = base_config.copy()
        config['build']['source_location'] = 'src.tar.gz'
        config['build']['extra_files'] = [
            'src.tar.gz',
            'src.xz',
        ]
        test = pav_test.PavTest(self.pav_cfg, config=config)

        if os.path.exists(test.build_origin):
            shutil.rmtree(test.build_origin)

        test._setup_build_dir(test.build_origin)

        for file in config['build']['extra_files']:
            self._cmp_files(os.path.join(test_archives, file),
                            os.path.join(test.build_origin, file))

    def test_src_urls(self):

        base_config = {
            'name': 'test',
            'build': {
                'modules': ['gcc'],
            }
        }

        config = base_config.copy()
        config['build']['source_location'] = self.TEST_URL

        test = pav_test.PavTest(self.pav_cfg, config)
        if os.path.exists(test.build_origin):
            shutil.rmtree(test.build_origin)
        test._setup_build_dir(test.build_origin)
        self._cmp_files(os.path.join(self.TEST_DATA_ROOT, '../../README.md'),
                        os.path.join(test.build_origin, 'README.md'))

    def test_resolve_template(self):
        tmpl_path = os.path.join(self.TEST_DATA_ROOT, 'resolve_template_good.tmpl')

        var_man = variables.VariableSetManager()
        var_man.add_var_set('sched', {
            'num_nodes': '3',
            'partition': 'test'
        })
        var_man.add_var_set('sys', {
            'hostname': 'test.host.com',
            'complicated': {
                'a': 'yes',
                'b': 'no'
            }
        })

        script_path = tempfile.mktemp()
        pav_test.PavTest.resolve_template(tmpl_path,
                                          script_path,
                                          var_man)
        with open(script_path) as gen_script,\
             open(os.path.join(self.TEST_DATA_ROOT, 'resolve_template_good.sh')) as ver_script:
            self.assertEqual(gen_script.read(), ver_script.read())

        os.unlink(script_path)

        for bad_tmpl in (
                'resolve_template_keyerror.tmpl',
                'resolve_template_bad_key.tmpl',
                'resolve_template_extra_escape.tmpl'):

            script_path = tempfile.mktemp()
            tmpl_path = os.path.join(self.TEST_DATA_ROOT, bad_tmpl)
            with self.assertRaises(KeyError,
                                   msg="Error not raised on bad file '{}'".format(bad_tmpl)):
                pav_test.PavTest.resolve_template(tmpl_path, script_path, var_man)

            if os.path.exists(script_path):
                os.unlink(script_path)

    def test_build(self):
        """Make sure building works."""

        config1 = {
            'name': 'build_test',
            'build': {
                'cmds': ['echo "Hello World [\x1esched.num_nodes\x1e]"'],
                'source_location': 'binfile.gz',
            },
        }

        sched_vars = {
            'num_nodes': '3'
        }

        test = pav_test.PavTest(self.pav_cfg, config1)

        # Test a basic build, with a gzip file and an actual build script.
        self.assertTrue(test.build(sched_vars), msg="Build failed")

        # Make sure the build path and build origin contain softlinks to the same files.
        self._cmp_tree(test.build_origin, test.build_path)
        self._is_softlink_dir(test.build_path)

        # We're going to time out this build on purpose, to test the code that waits for
        # builds to complete.
        config = {
            'name': 'build_test',
            'build': {
                'cmds': ['sleep 10'],
                'source_location': 'binfile.gz',
            },
        }

        test = pav_test.PavTest(self.pav_cfg, config)
        test.BUILD_SILENT_TIMEOUT = 1

        # This build should fail.
        self.assertFalse(test.build(sched_vars), "Build succeeded when it should have timed out.")
        self.assertTrue(test.status.current().note.startswith("Build timed out"))

        # Test general build failure.
        config = {
            'name': 'build_test',
            'build': {
                'cmds': ['exit 1'],
                'source_location': 'binfile.gz',
            },
        }

        # These next two test a few things:
        #  1. That building, and then re-using, a build directory works.
        #  2. That the test fails properly under a couple different conditions
        test = pav_test.PavTest(self.pav_cfg, config)
        # Remove the build tree to ensure we do the build fresh.
        shutil.rmtree(test.build_origin)

        # This should fail because the build exits non-zero
        self.assertFalse(test.build(sched_vars), "Build succeeded when it should have failed.")
        self.assertTrue(test.status.current().note.startswith("Build returned a non-zero result."))

        # This should fail due to a missing variable
        # The build should already exist.
        test2 = pav_test.PavTest(self.pav_cfg, config)
        self.assertFalse(test2.build({}), "Build succeeded when it should have had a variable "
                                          "error")
        self.assertTrue(test2.status.current().note.startswith("Error resolving variable."))

        self.assertEqual(test.build_origin, test2.build_origin)

    def test_run(self):
        pass

    def _is_softlink_dir(self, path):
        """Verify that a directory contains nothing but softlinks whose files exist. Directories
        in a softlink dir should be real directories though."""

        for base_dir, cdirs, cfiles in os.walk(path):
            for cdir in cdirs:
                self.assert_(os.path.isdir(os.path.join(base_dir, cdir)),
                             "Directory in softlink dir is a softlink (it shouldn't be).")

            for file in cfiles:
                file_path = os.path.join(base_dir, file)
                self.assert_(os.path.islink(file_path),
                             "File in softlink dir '{}' is not a softlink."
                             .format(file_path))

                target_path = os.path.realpath(file_path)
                self.assert_(os.path.exists(target_path),
                             "Softlink target '{}' for link '{}' does not exist."
                             .format(target_path, file_path))

    def _cmp_files(self, a_path, b_path):
        """Compare two files."""

        with open(a_path, 'rb') as a_file, open(b_path, 'rb') as b_file:
            self.assertEqual(a_file.read(), b_file.read(),
                             "File contents mismatch for {} and {}."
                             .format(a_path, b_path))

    def _cmp_tree(self, a, b):
        """Compare two directory trees, including the contents of all the files."""

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

                self._cmp_files(a_path, b_path)

        self.assert_(not a_walk and not b_walk,
                     "Left over directory contents in a or b: {}, {}".format(a_walk, b_walk))

