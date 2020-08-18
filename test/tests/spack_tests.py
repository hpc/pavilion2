import io
from pathlib import Path
import re

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import test_run
from pavilion.unittest import PavTestCase


class SpackTests(PavTestCase):

    def setUp(self):

        self.pav_cfg['spack_path'] = Path('~/a/fake/path')
        self.working_dir = self.pav_cfg['working_dir']
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    def test_spack_build(self):
        """Test to ensure that a test is built correctly."""

        # This test contains spack commands
        arg_parser = arguments.get_parser()
        args = arg_parser.parse_args([
            'build',
            'spack_test.spack_stuff'
        ])

        build_cmd = commands.get_command(args.command_name)
        build_cmd.silence()
        # This will result in a build error, as I didn't provide a real spack
        # path. That is ok as I only need to check the generated build script.
        build_cmd.run(self.pav_cfg, args)

        test_dir = self.working_dir/'test_runs'/'0000001'
        spack_build_env = test_dir/'build'/'spack.yaml'

        # We should have created a spack.yaml (spack build env) file.
        self.assertTrue(spack_build_env.exists())

        build_script_path = test_dir/'build.sh'
        with build_script_path.open('r') as build_script:
            build_script_str = build_script.read()

        # Ensure the spack commands get placed in the build_script correctly
        self.assertTrue("source ~/a/fake/path/share/spack/setup-env.sh" in
                        build_script_str)
        self.assertTrue("spack env activate -V ." in build_script_str)
        self.assertTrue("spack install stuff" in build_script_str)
