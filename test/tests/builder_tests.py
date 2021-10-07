import copy
import io
import os
import pathlib
import shutil
import stat
import threading
import time
import unittest

from pavilion import plugins
from pavilion import wget
from pavilion.status_file import STATES
from pavilion.test_run import TestRun
from pavilion.unittest import PavTestCase


class BuilderTests(PavTestCase):

    def setUp(self) -> None:
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self) -> None:
        plugins._reset_plugins()

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
            'foo/bar/deep.zip',
            '../outside.zip',
        ]

        test_archives = self.TEST_DATA_ROOT/'pav_config_dir'/'test_src'
        original_tree = test_archives/'src'

        for archive in archives:
            config = copy.deepcopy(base_config)
            config['build']['source_path'] = archive
            config['build']['specificity'] = archive

            test = self._quick_test(config, build=False, finalize=False)

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
        config['build']['source_path'] = 'src'
        test = self._quick_test(config, build=False, finalize=False)

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
            config['build']['source_path'] = file
            test = self._quick_test(config, build=False, finalize=False)

            if test.builder.path.exists():
                shutil.rmtree(str(test.builder.path))

            test.builder._setup_build_dir(test.builder.path)
            self._cmp_files(test.builder.path/'binfile',
                            original_tree/'binfile')

        # Make sure extra files are getting copied over.
        config = copy.deepcopy(base_config)
        config['build']['source_path'] = 'src.tar.gz'
        config['build']['extra_files'] = [
            'src.tar.gz',
            'src.xz',
            '../outside.zip',
            'foo/bar/deep.zip',
        ]

        test = self._quick_test(config, build=False, finalize=False)

        if test.builder.path.exists():
            shutil.rmtree(str(test.builder.path))

        test.builder._setup_build_dir(test.builder.path)

        for file in config['build']['extra_files']:
            file = pathlib.Path(file)
            self._cmp_files(test_archives/file,
                            test.builder.path/file.name)

    def test_create_file(self):
        """Check that build time file creation is working correctly."""

        files_to_create = {
            'file1': ['line_0', 'line_1'],
            'wild/file2': ['line_0', 'line_1'],  # wild dir exists
            'wild/dir2/file3': ['line_0', 'line_1'],  # dir2 does not exist
            'real.txt': ['line1', 'line4']  # file exists
        }
        config = self._quick_test_cfg()
        config['build']['source_path'] = 'file_tests.tgz'
        config['build']['create_files'] = files_to_create
        test = self._quick_test(config)

        for file, lines in files_to_create.items():
            file_path = test.path/'build'/file
            self.assertTrue(file_path.exists())

            # Stage file contents for comparison.
            original = io.StringIO()
            for line in lines:
                original.write("{}\n".format(line))
            created_file = open(str(file_path), 'r', encoding='utf-8')

            # Compare contents.
            self.assertEquals(original.getvalue(), created_file.read())
            original.close()
            created_file.close()

    def test_create_file_errors(self):
        """Check build time file creation expected errors."""

        # Ensure a file can't be written outside the build context.
        files_to_fail = ['../file', '../../file', 'wild/../../file']
        for file in files_to_fail:
            file_arg = {file: []}
            config = self._quick_test_cfg()
            config['build']['source_path'] = 'file_tests.tgz'
            config['build']['create_files'] = file_arg
            with self.assertRaises(RuntimeError) as context:
                self._quick_test(config)
            self.assertTrue('outside build context' in str(context.exception))

        # Ensure a file can't overwrite existing directories.
        files_to_fail = ['wild', 'rec']
        for file in files_to_fail:
            file_arg = {file: []}
            config = self._quick_test_cfg()
            config['build']['source_path'] = 'file_tests.tgz'
            config['build']['create_files'] = file_arg
            test = self._quick_test(config, build=False, finalize=False)
            self.assertFalse(test.build())

    def test_copy_build(self):
        """Check that builds are copied correctly."""

        config = self._quick_test_cfg()
        # The copy_test source file contains several files to copy
        # for real and several to symlink.
        config['build']['source_path'] = 'file_tests.tgz'
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
            # Make sure the copied files are writable.
            mode = real.stat().st_mode
            self.assertTrue(mode & stat.S_IWGRP)
            self.assertTrue(mode & stat.S_IWUSR)

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

    @unittest.skipIf(wget.missing_libs(),
                     "The wget module is missing required libs.")
    def test_src_urls(self):

        config_dir = self.TEST_DATA_ROOT/'pav_config_dir'

        config = {
            'name': 'test',
            'scheduler': 'raw',
            'suite_path': (config_dir/'tests'/'fake_test.yaml').as_posix(),
            'build': {
                'modules': ['gcc'],
                'source_url': self.TEST_URL,
                'source_path': 'README.md',
                'source_download': 'missing',
            }
        }

        expected_path = config_dir/'test_src'/'README.md'
        if expected_path.exists():
            expected_path.unlink()

        self.assertFalse(expected_path.exists())

        test = self._quick_test(config, build=False, finalize=False)
        test.builder._setup_build_dir(test.builder.path)

        self.assertEqual(self.TEST_URL_HASH,
                         self.get_hash(test.builder.path/'README.md'))
        self.assertTrue(expected_path.exists())

        # Make sure the build isn't updated even the local is different.
        with expected_path.open('a') as readme_file:
            readme_file.write("<extra>")
        orig_time = expected_path.stat().st_mtime
        self._quick_test(config, build=False, finalize=False)
        self.assertEqual(orig_time, expected_path.stat().st_mtime)

        # Here it should be updated. We're playing a weird trick here though,
        # by pointing to a completely different url.
        config = copy.deepcopy(config)
        config['build']['source_url'] = self.TEST_URL2
        config['build']['source_download'] = 'latest'
        self._quick_test(config, build=False, finalize=False)
        self.assertGreater(expected_path.stat().st_mtime, orig_time)

        config = copy.deepcopy(config)
        config['build']['source_download'] = 'never'
        config['build']['source_url'] = 'http://nowhere-that-exists.com'
        self._quick_test(config, build=False, finalize=False)
        # This should succeed, because the file exists and we're not
        # going to download it.

    def test_build(self):
        """Make sure building works."""

        config1 = {
            'name': 'build_test',
            'scheduler': 'raw',
            'build': {
                'timeout': '12',
                'cmds': ['echo "Hello World [\x1esched.num_nodes\x1e]"'],
                'source_path': 'binfile.gz',
            },
        }

        test = self._quick_test(config1, build=False, finalize=False)

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
                'source_path': 'binfile.gz',
            },
        }

        test = self._quick_test(config, 'build_test', build=False,
                                finalize=False)

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
                'source_path': 'binfile.gz',
            },
        }

        #  Check that building, and then re-using, a build directory works.
        test = self._quick_test(config, 'build_test', build=False,
                                finalize=False)

        # Remove the build tree to ensure we do the build fresh.
        if test.builder.path.is_dir():
            shutil.rmtree(str(test.builder.path))
        self.assertTrue(test.build())

        test2 = self._quick_test(config, 'build_test', build=False,
                                 finalize=False)
        self.assertTrue(test2.build())
        self.assertEqual(test.builder.path, test2.builder.path)

        config3 = copy.deepcopy(config)
        config3['build']['cmds'] = ['exit 1']
        # This should fail because the build exits non-zero
        test3 = self._quick_test(config3, 'build_test', build=False,
                                 finalize=False)
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
        test = self._quick_test(config, 'build_test', build=False,
                                finalize=False)

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
