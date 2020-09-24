import io
import os
import unittest
from pathlib import Path

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import series
from pavilion import test_run
from pavilion.unittest import PavTestCase


class SpackTests(PavTestCase):

    def setUp(self):

        self.working_dir = self.pav_cfg['working_dir']
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_spack_build(self):
        """Test to ensure that a test is built correctly."""

        # This test contains spack commands
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'run',
            'spack_test'
        ])

        run_cmd = commands.get_command(args.command_name)
        run_cmd.silence()
        run_cmd.run(self.pav_cfg, args)

        series_id = series.TestSeries.load_user_series_id(self.pav_cfg)
        test_obj = list(series.TestSeries.from_id(self.pav_cfg,
                                                  series_id)
                        .tests.values())[0]

        build_name = test_obj.build_name
        test_id = str(test_obj.id)

        args = arg_parser.parse_args([
            'wait',
            test_id
        ])

        wait_cmd = commands.get_command(args.command_name)
        wait_cmd.silence()
        wait_cmd.run(self.pav_cfg, args)

        args = arg_parser.parse_args([
            'cat',
            test_id,
            'build.log'
        ])

        test_dir = self.working_dir/'test_runs'/test_id.zfill(7)
        spack_build_env = test_dir/'build'/'spack.yaml'

        # We should have created a spack.yaml (spack build env) file.
        self.assertTrue(spack_build_env.exists())

        build_script_path = test_dir/'build.sh'
        with build_script_path.open('r') as build_script:
            build_script_str = build_script.read()

        # Ensure the spack commands get placed in the build_script correctly.
        self.assertTrue("source {}/share/spack/setup-env.sh"
                        .format(self.pav_cfg.get('spack_path')) in
                        build_script_str)
        self.assertTrue("spack env activate -d ." in build_script_str)
        self.assertTrue("spack install activemq" in build_script_str)

        build_log_path = test_dir/'build.log'
        with build_log_path.open('r') as build_log:
            build_log_str = build_log.read()

        # Ensure spack package is installed. The plus lets us know the package
        # was successfully added as a spec to the env. 
        self.assertTrue("[+]" in build_log_str)

        # Ensure spack package is installed in the correct location. If it
        # installed correctly, this directory should not be empty. 
        spack_install_dir = test_dir/'build'/'spack_installs'
        self.assertIsNot(os.listdir(str(spack_install_dir)), [])

        # Ensure spack package can be loaded in the build section. Will only
        # see the following if the package install was unsuccessful.
        self.assertFalse("==> Error: Spec 'activemq' matches no installed "
                         "packages." in build_log_str)

        run_log_path = test_dir/'run.log'
        with run_log_path.open('r') as run_log:
            run_log_str = run_log.read()

        # Ensure spack package can be loaded in the run section. 
        self.assertFalse("==> Error: Spec 'activemq' matches no installed "
                         "packages." in run_log_str)

        # Demonstrates it is using the package installed in it's build dir.
        self.assertTrue("/builds/{}/spack_installs/".format(build_name) in
                        run_log_str)
