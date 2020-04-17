import copy
import io
import shutil
import threading
import time
import unittest

from pavilion import wget
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase
from pavilion import plugins


class BuilderTests(PavTestCase):

    def test_setup_build_dir(self):
        """Make sure we can correctly handle all of the various archive
        formats."""

        base_config = {
            'name': 'test',
            'scheduler': 'raw',
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
            'softlink.zip',
        ]

        test_archives = self.TEST_DATA_ROOT/'pav_config_dir'/'test_src'
        original_tree = test_archives/'src'

        for archive in archives:
            config = copy.deepcopy(base_config)
            config['build']['source_location'] = archive
            config['build']['specificity'] = archive

            test = TestRun(self.pav_cfg, config)

            tmp_path = test.builder.path.with_suffix('.test')

            test.builder._setup_build_dir(test.builder.path)

            # Make sure the extracted archive is identical to the original
            # (Though the containing directory will have a different name)
            try:
                self._cmp_tree(test.builder.path, original_tree)
            except AssertionError as err:
                raise AssertionError("Error extracting {}".format(archive),
                                     *err.args)

        # Check directory copying
        config = copy.deepcopy(base_config)
        config['build']['source_location'] = 'src'
        test = TestRun(self.pav_cfg, config)

        if test.builder.path.exists():
            shutil.rmtree(str(test.builder.path))

        test.builder._setup_build_dir(test.builder.path)
        self._cmp_tree(test.builder.path, original_tree)

        # Test single compressed files.
        files = [
            'binfile.gz',
            'binfile.bz2',
            'binfile.xz',
        ]

        for file in files:
            config = copy.deepcopy(base_config)
            config['build']['source_location'] = file
            test = TestRun(self.pav_cfg, config)

            if test.builder.path.exists():
                shutil.rmtree(str(test.builder.path))

            test.builder._setup_build_dir(test.builder.path)
            self._cmp_files(test.builder.path/'binfile',
                            original_tree/'binfile')

        # Make sure extra files are getting copied over.
        config = copy.deepcopy(base_config)
        config['build']['source_location'] = 'src.tar.gz'
        config['build']['extra_files'] = [
            'src.tar.gz',
            'src.xz',
        ]

        test = TestRun(self.pav_cfg, config)

        if test.builder.path.exists():
            shutil.rmtree(str(test.builder.path))

        test.builder._setup_build_dir(test.builder.path)

        for file in config['build']['extra_files']:
            self._cmp_files(test_archives/file,
                            test.builder.path/file)

    def test_make_file_build(self):
        """Check that build time file creation is working correctly."""

        plugins.initialize_plugins(pav.pav_cfg)
        files_to_make = {
            'file1': ['line_0', 'line_1'],
            'dir1/file2': ['line_0', 'line_1'],  # dir1 exists
            'dir1/dir2/file3': ['line_0', 'line_1']  # dir2 does not exist
        }
        config = self._quick_test_cfg()
        config['build']['source_location'] = 'make_files.tgz'
        config['build']['make_files'] = files_to_make
        test = self._quick_test(config)

        for file, lines in files_to_make.items():
            file_path = test.path/'build'/file
            self.assertTrue(file_path.exists())

            # Stage file contents for comparison.
            original = io.StringIO()
            original.write("{}\n".format(file_to_make[file]))
            for line in lines:
                original.write("{}\n".format(line))
            created_file = open(file_path, 'r', encoding='utf-8')

            # Compare contents.
            self.assertTrue(original.getvalue() == created_file.read())
            original.close()
            created_file.close()

    def test_copy_build(self):
        """Check that builds are copied correctly."""

        plugins.initialize_plugins(self.pav_cfg)

        config = self._quick_test_cfg()
        # The copy_test source file contains several files to copy
        # for real and several to symlink.
        config['build']['source_location'] = 'copy_test.tgz'
        config['build']['copy_files'] = [
            'real.*',
            'wild/real_?i*[0-9].dat',
            'rec/**/real*',
        ]

        test = self._quick_test(config)

        # Make sure the following exist and are regular files.
        real_files = [
            'real.txt',
            'wild/real_wild1.dat',
            'wild/real_wild2.dat',
            'rec/real_r1.txt',
            'rec/rec2/real_r2.txt'
        ]

        for real in real_files:
            real = test.path/'build'/real

            self.assertTrue(real.exists(),
                            msg="Missing {}".format(real))
            self.assertTrue(real.is_file(),
                            msg="{} is not a regular file.".format(real))

        # Make sure the following exist, but are symlinks.
        sym_files = [
            'pav_build_log',
            '.built_by',
            'sym.txt',
            'wild/sym.dat',
            'rec/sym_r1.txt',
            'rec/rec2/sym_r2.txt',
        ]

        for sym in sym_files:
            sym = test.path/'build'/sym
            self.assertTrue(sym.exists(),
                            msg="Missing {}".format(sym))
            self.assertTrue(sym.is_symlink(),
                            msg="{} is not a symlink".format(sym))

        plugins._reset_plugins()

    README_HASH = '275fa3c8aeb10d145754388446be1f24bb16fb00'

    @unittest.skipIf(wget.missing_libs(),
                     "The wget module is missing required libs.")
    def test_src_urls(self):

        base_config = {
            'name': 'test',
            'scheduler': 'raw',
            'build': {
                'modules': ['gcc'],
            }
        }

        config = copy.deepcopy(base_config)
        config['build']['source_location'] = self.TEST_URL

        # remove existing downloads, and replace the directory.
        downloads_path = self.pav_cfg.working_dir/'downloads'
        shutil.rmtree(str(downloads_path))
        downloads_path.mkdir()

        test = TestRun(self.pav_cfg, config)
        if test.builder.path.exists():
            shutil.rmtree(str(test.builder.path))

        test.builder._setup_build_dir(test.builder.path)
        self.assertEqual(self.README_HASH,
                         self.get_hash(test.builder.path/'README.md'))

    def test_build(self):
        """Make sure building works."""

        config1 = {
            'name': 'build_test',
            'scheduler': 'raw',
            'build': {
                'timeout': '12',
                'cmds': ['echo "Hello World [\x1esched.num_nodes\x1e]"'],
                'source_location': 'binfile.gz',
            },
        }

        test = TestRun(self.pav_cfg, config1)

        # Test a basic build, with a gzip file and an actual build script.
        self.assertTrue(test.build(), msg="Build failed")

        # Make sure the build path and build origin contain softlinks to the
        # same files.
        self._cmp_tree(test.builder.path, test.build_path)
        self._is_softlink_dir(test.build_path)

        # We're going to time out this build on purpose, to test the code
        # that waits for builds to complete.
        config = {
            'name': 'build_test',
            'scheduler': 'raw',
            'build': {
                'timeout': '1',
                'cmds': ['sleep 10'],
                'source_location': 'binfile.gz',
            },
        }

        test = TestRun(self.pav_cfg, config)

        # This build should fail.
        self.assertFalse(test.build(),
                         "Build succeeded when it should have timed out.")
        current_note = test.status.current().note
        self.assertTrue(current_note.startswith("Build timed out"))

        # Test general build failure.
        config = {
            'name': 'build_test',
            'scheduler': 'raw',
            'build': {
                'timeout': '12',
                'cmds': ['exit 0'],
                'source_location': 'binfile.gz',
            },
        }

        #  Check that building, and then re-using, a build directory works.
        test = TestRun(self.pav_cfg, config)

        # Remove the build tree to ensure we do the build fresh.
        if test.builder.path.is_dir():
            shutil.rmtree(str(test.builder.path))
        self.assertTrue(test.build())

        test2 = TestRun(self.pav_cfg, config)
        self.assertTrue(test2.build())
        self.assertEqual(test.builder.path, test2.builder.path)

        config3 = copy.deepcopy(config)
        config3['build']['cmds'] = ['exit 1']
        # This should fail because the build exits non-zero
        test3 = TestRun(self.pav_cfg, config3)
        self.assertFalse(test3.build(),
                         "Build succeeded when it should have failed.")
        current_note = test3.status.current().note
        self.assertTrue(current_note.startswith(
            "Build returned a non-zero result."))

    def test_builder_cancel(self):
        """Check build canceling through their threading event."""

        cancel_event = threading.Event()

        config = {
            'name': 'build_test',
            'scheduler': 'raw',
            'build': {
                'timeout': '11',
                'cmds': ['sleep 5'],
            },
        }

        #  Check that building, and then re-using, a build directory works.
        test = TestRun(self.pav_cfg, config)

        thread = threading.Thread(
            target=test.build,
            args=(cancel_event,)
        )
        thread.start()

        # Wait for the test to actually start building.
        timeout = 5 + time.time()
        states = [stat.state for stat in test.status.history()]
        while STATES.BUILDING not in states:
            if time.time() > timeout:
                self.fail("Test {} did not complete within 5 seconds."
                          .format(test.id))
            time.sleep(.5)
            states = [stat.state for stat in test.status.history()]

        time.sleep(.2)
        cancel_event.set()

        try:
            thread.join(timeout=1)
        except TimeoutError:
            self.fail("Build did not respond quickly enough to being canceled.")

        self.assertEqual(test.status.current().state, STATES.ABORTED)
