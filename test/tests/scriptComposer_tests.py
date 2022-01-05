import grp, os, pwd, stat, sys, unittest
from pathlib import Path
from collections import OrderedDict
from pavilion import scriptcomposer
from pavilion.unittest import PavTestCase
from pavilion import utils

class TestScriptWriter(PavTestCase):

    script_path = 'testName.batch'

    def setUp(self):
        """Set up for the ScriptComposer tests."""
        if os.path.exists(self.script_path):
            os.remove(self.script_path)

    def _other_group(self):
        """Find a group other than the user's default group to use when creating files.
        :returns: The name of the found group."""

        for gid in os.getgroups():

            if gid == os.getgid():
                # This is the user's default.
                continue

            return grp.getgrgid(gid).gr_name

        raise RuntimeError("Could not find suitable group for use in test.")

    def test_header(self):
        """Test for the ScriptHeader class."""

        header = scriptcomposer.ScriptHeader(
            shebang="#!/bin/sh",
        )

        self.assertEqual(header.get_lines(),
                         ['#!/bin/sh'])

    def test_script_composer(self):
        """Testing ScriptComposer class variable setting."""

        # Testing valid uses.

        # Testing initialization defaults.
        composer = scriptcomposer.ScriptComposer()

        self.assertEqual(composer.header.shebang, '#!/bin/bash')

        # Testing individual assignment
        test_header_shell = "/usr/env/python"

        composer.newline()

        composer.command('taco')
        composer.command('burrito')
        composer.command('nachos')

        composer.header.shebang = test_header_shell

        self.assertEqual(composer.header.shebang, test_header_shell)

        composer = scriptcomposer.ScriptComposer()

        self.assertEqual(composer.header.shebang, '#!/bin/bash')

        # Testing object assignment.
        header = scriptcomposer.ScriptHeader(
            shebang=test_header_shell)

        composer.header = header

        self.assertEqual(composer.header.shebang, test_header_shell)

    def test_write_script(self):
        """Testing the writeScript function of the ScriptComposer class."""

        test_header_shell = "/usr/env/python"

        path = self.pav_cfg.working_dir/'testPath'

        testComposer = scriptcomposer.ScriptComposer()

        testComposer.header.shebang = test_header_shell

        testComposer.write(path)

        self.assertTrue(path.exists())

        with path.open() as test_file:
            test_lines = test_file.readlines()

        for i in range(0, len(test_lines)):
            test_lines[i] = test_lines[i].strip()

        self.assertEqual(test_lines[0], "#!/usr/env/python")
        self.assertEqual(test_lines[1], "")
        self.assertEqual(test_lines[2], "")

        test_stat = path.stat()

        umask = os.umask(0)
        os.umask(umask)
        # Default file permissions.
        expected_stat = (0o100666 & ~umask) | stat.S_IXGRP | stat.S_IXUSR

        self.assertEqual(oct(test_stat.st_mode), oct(expected_stat))

        path.unlink()
