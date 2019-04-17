import os
import shutil
import tempfile

from pavilion.test_config import PavTest, variables
from pavilion.test_config.test import PavTestError
from pavilion.suite import Suite

from pavilion import unittest


class PavTestTests(unittest.PavTestBase):

    def test_obj(self):
        """Test pavtest object initialization."""

        # Initializing with a mostly blank config
        config = {
            # The only required param.
            'name': 'blank_test'
        }

        # Making sure this doesn't throw errors from missing params.
        PavTest(self.pav_cfg, config)

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
        t = PavTest(self.pav_cfg, config)

        # Make sure we can recreate the object from id.
        t2 = PavTest.from_id(self.pav_cfg, t.id)

        # Make sure the objects are identical
        # This tests the following functions
        #  - from_id
        #  - save_config, load_config
        #  - get_test_path
        #  - write_tmpl
        for key in set(t.__dict__.keys()).union(t2.__dict__.keys()):
            self.assertEqual(t.__dict__[key], t2.__dict__[key])

    def test_setup_build_dir(self):
        """Make sure we can correctly handle all of the various archive
        formats."""

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

        test_archives = os.path.join(self.TEST_DATA_ROOT, 'pav_config_dir',
                                     'test_src')
        original_tree = os.path.join(test_archives, 'src')

        for archive in archives:
            config = base_config.copy()
            config['build']['source_location'] = archive

            test = PavTest(self.pav_cfg, config=config)

            if os.path.exists(test.build_origin):
                shutil.rmtree(test.build_origin)

            test._setup_build_dir(test.build_origin)

            # Make sure the extracted archive is identical to the original
            # (Though the containing directory will have a different name)
            try:
                self._cmp_tree(test.build_origin, original_tree)
            except AssertionError as err:
                raise AssertionError("Error extracting {}".format(archive),
                                     *err.args)

        # Check directory copying
        config = base_config.copy()
        config['build']['source_location'] = 'src'
        test = PavTest(self.pav_cfg, config=config)

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
            test = PavTest(self.pav_cfg, config=config)

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
        test = PavTest(self.pav_cfg, config=config)

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

        # remove existing downloads, and replace the directory.
        downloads_path = os.path.join(self.pav_cfg.working_dir, 'downloads')
        shutil.rmtree(downloads_path)
        os.mkdir(downloads_path)

        test = PavTest(self.pav_cfg, config)
        if os.path.exists(test.build_origin):
            shutil.rmtree(test.build_origin)

        test._setup_build_dir(test.build_origin)
        self._cmp_files(os.path.join(self.TEST_DATA_ROOT, '../../README.md'),
                        os.path.join(test.build_origin, 'README.md'))

    def test_resolve_template(self):
        tmpl_path = os.path.join(self.TEST_DATA_ROOT,
                                 'resolve_template_good.tmpl')

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
        PavTest.resolve_template(tmpl_path, script_path, var_man)
        good_path = os.path.join(self.TEST_DATA_ROOT,
                                 'resolve_template_good.sh')

        with open(script_path) as gen_script,\
             open(good_path) as ver_script:
            self.assertEqual(gen_script.read(), ver_script.read())

        os.unlink(script_path)

        for bad_tmpl in (
                'resolve_template_keyerror.tmpl',
                'resolve_template_bad_key.tmpl'):

            script_path = tempfile.mktemp()
            tmpl_path = os.path.join(self.TEST_DATA_ROOT, bad_tmpl)
            with self.assertRaises(
                    KeyError,
                    msg="Error not raised on bad file '{}'".format(bad_tmpl)):
                PavTest.resolve_template(tmpl_path, script_path, var_man)

            if os.path.exists(script_path):
                os.unlink(script_path)

        script_path = tempfile.mktemp()
        tmpl_path = os.path.join(self.TEST_DATA_ROOT,
                                 'resolve_template_extra_escape.tmpl')
        with self.assertRaises(
                PavTestError,
                msg="Error not raised on bad file '{}'".format(bad_tmpl)):
            PavTest.resolve_template(tmpl_path, script_path, var_man)

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

        test = PavTest(self.pav_cfg, config1)

        # Test a basic build, with a gzip file and an actual build script.
        self.assertTrue(test.build(), msg="Build failed")

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

        test = PavTest(self.pav_cfg, config)
        test.BUILD_SILENT_TIMEOUT = 1

        # This build should fail.
        self.assertFalse(test.build(), "Build succeeded when it should have timed out.")
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
        test = PavTest(self.pav_cfg, config)
        # Remove the build tree to ensure we do the build fresh.
        if os.path.isdir(test.build_origin):
            shutil.rmtree(test.build_origin)

        # This should fail because the build exits non-zero
        self.assertFalse(test.build(), "Build succeeded when it should have failed.")
        self.assertTrue(test.status.current().note.startswith("Build returned a non-zero result."))

        # This should fail due to a missing variable
        # The build should already exist.
        test2 = PavTest(self.pav_cfg, config)
        self.assertFalse(test2.build(), "Build succeeded when it should have failed.")
        self.assertTrue(test.status.current().note.startswith("Build returned a non-zero result."))

        self.assertEqual(test.build_origin, test2.build_origin)

    def test_run(self):
        config1 = {
            'name': 'run_test',
            'run': {
                'env': {
                    'foo': 'bar',
                },
                #
                'cmds': ['echo "I ran, punks"'],
            },
        }

        test = PavTest(self.pav_cfg, config1)

        self.assertTrue(test.run({}), msg="Test failed to run.")

        config2 = config1.copy()
        config2['run']['modules'] = ['asdlfkjae', 'adjwerloijeflkasd']

        test = PavTest(self.pav_cfg, config2)
        self.assertFalse(
            test.run({}),
            msg="Test should have failed because a module couldn't be "
                "loaded. {}".format(test.path))
        # TODO: Make sure this is the exact reason for the failure
        #   (doesn't work currently).

        # Make sure the test fails properly on a timeout.
        config3 = {
            'name': 'sleep_test',
            'run': {
                'cmds': ['sleep 10']
            }
        }
        test = PavTest(self.pav_cfg, config3)
        test.RUN_SILENT_TIMEOUT = 1
        self.assertFalse(test.run({}),
                         msg="Test should have failed due to timeout. {}"
                             .format(test.path))

    def test_suites(self):
        """Test suite creation and regeneration."""

        config1 = {
            'name': 'run_test',
            'run': {
                'env': {
                    'foo': 'bar',
                },
                #
                'cmds': ['echo "I ran, punks"'],
            },
        }

        tests = []
        for i in range(3):
            tests.append(PavTest(self.pav_cfg, config1))

        # Make sure this doesn't explode
        suite = Suite(self.pav_cfg, tests)

        # Make sure we got all the tests
        self.assertEqual(len(suite.tests), 3)
        test_paths = [os.path.join(suite.path, p)
                      for p in os.listdir(suite.path)]
        # And that the test paths are unique
        self.assertEqual(len(set(test_paths)),
                         len([os.path.realpath(p) for p in test_paths]))

        self._is_softlink_dir(suite.path)

        suite2 = Suite.from_id(self.pav_cfg, suite.id)
        self.assertEqual(sorted(suite.tests.keys()),
                         sorted(suite2.tests.keys()))
        self.assertEqual([t.id for t in suite.tests.values()],
                         [t.id for t in suite2.tests.values()])
                                                
        self.assertEqual(suite.path, suite2.path)
        self.assertEqual(suite.id, suite2.id)

