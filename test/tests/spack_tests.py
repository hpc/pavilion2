import io
from pathlib import Path
import re
import unittest

from pavilion import arguments
from pavilion import commands
from pavilion import plugins
from pavilion import test_run
from pavilion.unittest import PavTestCase
from pavilion.plugins.commands.status import get_tests

_HAS_SPACK = None


def has_spack():
    global _HAS_SPACK
    if _HAS_SPACK is None:
        return False

    return True


class SpackTests(PavTestCase):

    def setUp(self):

        global _HAS_SPACK
        _HAS_SPACK = self.pav_cfg.get('spack_path', None)
        self.working_dir = self.pav_cfg['working_dir']
        plugins.initialize_plugins(self.pav_cfg)

    def tearDown(self):

        plugins._reset_plugins()

    @unittest.skipIf(not has_spack(), "No 'spack_path' defined.")
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

        args = arg_parser.parse_args([
            'status'
        ])

        test_id = str(get_tests(self.pav_cfg, args, io.StringIO())[0]).zfill(7)

        test_dir = self.working_dir/'test_runs'/test_id
        spack_build_env = test_dir/'build'/'spack.yaml'

        # We should have created a spack.yaml (spack build env) file.
        self.assertTrue(spack_build_env.exists())

        build_script_path = test_dir/'build.sh'
        with build_script_path.open('r') as build_script:
            build_script_str = build_script.read()

        # Ensure the spack commands get placed in the build_script correctly
        self.assertTrue("source {}/share/spack/setup_env.sh"
                        .format(Self.pav_cfg.get('spack_path')) in
                        build_script_str)
        self.assertTrue("spack env activate -d ." in build_script_str)
        self.assertTrue("spack install stuff" in build_script_str)
