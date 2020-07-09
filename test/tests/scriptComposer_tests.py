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
            scheduler_headers=[
                '# FOO',
                '# BAR',
            ]
        )

        self.assertEqual(header.get_lines(),
                         ['#!/bin/sh',
                          '# FOO',
                          '# BAR'])

    def test_scriptComposer(self):
        """Testing ScriptComposer class variable setting."""

        # Testing valid uses.

        # Testing initialization defaults.
        composer = scriptcomposer.ScriptComposer()

        self.assertEqual(composer.header.shebang, '#!/bin/bash')
        self.assertEqual(composer.header.scheduler_headers, [])

        # Testing individual assignment
        test_header_shell = "/usr/env/python"
        test_header_scheduler = OrderedDict()
        test_header_scheduler['-G'] = 'pam'
        test_header_scheduler['-N'] = 'fam'

        composer.newline()

        composer.command(['taco', 'burrito', 'nachos'])

        test_details_path = 'testPath'
        test_details_group = 'groupies'
        test_details_perms = 0o543

        composer.header.shebang = test_header_shell
        composer.header.scheduler_headers = test_header_scheduler

        self.assertEqual(composer.header.shebang, test_header_shell)
        self.assertEqual(composer.header.scheduler_headers,
                                                          test_header_scheduler)

        composer = scriptcomposer.ScriptComposer()

        self.assertEqual(composer.header.shebang, '#!/bin/bash')
        self.assertEqual(composer.header.scheduler_headers, [])

        # Testing object assignment.
        header = scriptcomposer.ScriptHeader(
            shebang=test_header_shell,
            scheduler_headers=test_header_scheduler)

        composer.header = header

        self.assertEqual(composer.header.shebang, test_header_shell)
        self.assertEqual(composer.header.scheduler_headers,
                                                          test_header_scheduler)

    def test_writeScript(self):
        """Testing the writeScript function of the ScriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = ['-G pam', '-N fam']

        path = self.pav_cfg.working_dir/'testPath'

        testComposer = scriptcomposer.ScriptComposer()

        testComposer.header.shebang = testHeaderShell
        testComposer.header.scheduler_headers = testHeaderScheduler

        testComposer.write(path)

        self.assertTrue(path.exists())

        with path.open() as testFile:
            testLines = testFile.readlines()

        for i in range(0, len(testLines)):
            testLines[i] = testLines[i].strip()

        self.assertEqual(testLines[0], "#!/usr/env/python")
        self.assertEqual(testLines[1], "# -G pam")
        self.assertEqual(testLines[2], "# -N fam")
        self.assertEqual(testLines[3], "")
        self.assertEqual(testLines[4], "")

        self.assertEqual(len(testLines), 5)

        testStat = path.stat()

        umask = os.umask(0)
        os.umask(umask)
        # Default file permissions.
        expectedStat = (0o100666 & ~umask) | stat.S_IXGRP | stat.S_IXUSR

        self.assertEqual(oct(testStat.st_mode), oct(expectedStat))

        path.unlink()
