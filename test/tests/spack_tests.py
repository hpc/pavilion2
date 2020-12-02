"""Test the functionality of the Spack integration."""

import os
import unittest
from pathlib import Path

from pavilion import plugins
from pavilion.unittest import PavTestCase


def has_spack_path():
    """Check if we have an activated spack install."""

    spack_path = Path(__file__).parents[1]/'spack'

    return spack_path.exists()


class SpackTests(PavTestCase):

    def setUp(self):

        self.working_dir = self.pav_cfg['working_dir']
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    @unittest.skipIf(not has_spack_path(), "spack dir does not exist")
    def test_spack_build(self):
        """Test to ensure that a test is built correctly."""

        cfg = self._quick_test_cfg()

        cfg['build']['spack'] = {
            'install': 'time',
            'load': 'time',
        }
        cfg['run']['spack'] = {
            'load': 'time'
        }
        cfg['run']['cmds'] = [
            'which time'
        ]

        test = self._quick_test(cfg, 'spack_build')
        test.run()
        spack_build_env = test.path/'build'/'spack.yaml'

        # We should have created a spack.yaml (spack build env) file.
        self.assertTrue(spack_build_env.exists())

        build_log_path = test.path/'build.log'
        with build_log_path.open() as build_log:
            build_log_str = build_log.read()

        # Ensure spack package is installed. The plus lets us know the package
        # was successfully added as a spec to the env.
        self.assertTrue("[+]" in build_log_str)

        # Ensure spack package is installed in the correct location. If it
        # installed correctly, this directory should not be empty.
        spack_install_dir = test.path/'build'/'spack_installs'
        self.assertIsNot(os.listdir(str(spack_install_dir)), [])

        # Ensure spack package can be loaded in the build section. Will only
        # see the following if the package install was unsuccessful.
        self.assertFalse("==> Error: Spec 'time' matches no installed "
                         "packages." in build_log_str,
                         msg="Build Log:\n{}".format(build_log_str))

        run_log_path = test.path/'run.log'
        with run_log_path.open() as run_log:
            run_log_str = run_log.read()

        # Ensure spack package can be loaded in the run section.
        self.assertFalse("==> Error: Spec 'time' matches no installed "
                         "packages." in run_log_str,
                         msg="Run Log:\n{}".format(run_log_str))

        # Demonstrates it is using the package installed in it's build dir.
        self.assertIn((test.builder.path/'spack_installs').as_posix(),
                      run_log_str,
                      msg="Run Log:\n{}".format(run_log_str))
