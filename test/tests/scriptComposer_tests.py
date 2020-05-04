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

    def test_details(self):
        """Testing the ScriptDetails class."""

        testPath = self.pav_cfg.working_dir/'testScript.sh'

        testGroup = 'anonymous'

        testPerms = 0o531

        # Testing valid uses.

        # Testing initialization and defaults.
        test_details = scriptcomposer.ScriptDetails()

        self.assertEqual(test_details.group, utils.get_login())
        self.assertEqual(test_details.perms, oct(0o770))

        # Testing individual assignment.
        test_details.path = testPath
        test_details.group = testGroup
        test_details.perms = testPerms

        self.assertEqual(test_details.path, Path(testPath))
        self.assertEqual(test_details.group, testGroup)
        self.assertEqual(test_details.perms, oct(testPerms))

        # Testing initialization assignment.
        test_details = scriptcomposer.ScriptDetails(path=testPath,
                                                    group=testGroup,
                                                    perms=testPerms)

        self.assertEqual(test_details.path, Path(testPath))
        self.assertEqual(test_details.group, testGroup)
        self.assertEqual(test_details.perms, oct(testPerms))

        test_details = scriptcomposer.ScriptDetails()

        # Testing invalid uses.
        with self.assertRaises(TypeError):
            test_details.path = True

        with self.assertRaises(TypeError):
            test_details.perms = 'string'

        with self.assertRaises(TypeError):
            test_details.perms = u'fail'

        with self.assertRaises(TypeError):
            test_details.perms = 7.5

        # Testing invalid initialization.
        with self.assertRaises(TypeError):
            scriptcomposer.ScriptDetails(path=testPath,
                                         group=testGroup,
                                         perms='fail')

    def test_scriptComposer(self):
        """Testing ScriptComposer class variable setting."""

        # Testing valid uses.

        # Testing initialization defaults.
        composer = scriptcomposer.ScriptComposer()

        self.assertIsInstance(composer.header,
                              scriptcomposer.ScriptHeader)
        self.assertIsInstance(composer.details,
                              scriptcomposer.ScriptDetails)

        self.assertEqual(composer.header.shebang, '#!/bin/bash')
        self.assertEqual(composer.header.scheduler_headers, [])

        self.assertEqual(composer.details.group, utils.get_login())
        self.assertEqual(composer.details.perms, oct(0o770))

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

        composer.details.path = test_details_path
        composer.details.group = test_details_group
        composer.details.perms = test_details_perms

        self.assertEqual(composer.header.shebang, test_header_shell)
        self.assertEqual(composer.header.scheduler_headers,
                                                          test_header_scheduler)

        self.assertEqual(composer.details.path, Path(test_details_path))
        self.assertEqual(composer.details.group, test_details_group)
        self.assertEqual(composer.details.perms, oct(test_details_perms))

        composer = scriptcomposer.ScriptComposer()

        self.assertEqual(composer.header.shebang, '#!/bin/bash')
        self.assertEqual(composer.header.scheduler_headers, [])

        self.assertEqual(composer.details.group, utils.get_login())
        self.assertEqual(composer.details.perms, oct(0o770))

        # Testing object assignment.
        header = scriptcomposer.ScriptHeader(
            shebang=test_header_shell,
            scheduler_headers=test_header_scheduler)

        testDetailsObj = scriptcomposer.ScriptDetails(
            path=test_details_path,
            group=test_details_group,
            perms=test_details_perms)

        composer.header = header
        composer.details = testDetailsObj

        self.assertEqual(composer.header.shebang, test_header_shell)
        self.assertEqual(composer.header.scheduler_headers,
                                                          test_header_scheduler)

        self.assertEqual(composer.details.path, Path(test_details_path))
        self.assertEqual(composer.details.group, test_details_group)
        self.assertEqual(composer.details.perms, oct(test_details_perms))


    def test_writeScript(self):
        """Testing the writeScript function of the ScriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = ['-G pam', '-N fam']

        testDetailsPath = self.pav_cfg.working_dir/'testPath'
        testDetailsGroup = self._other_group()
        testDetailsPerms = 0o760

        testComposer = scriptcomposer.ScriptComposer()

        testComposer.header.shebang = testHeaderShell
        testComposer.header.scheduler_headers = testHeaderScheduler

        testComposer.details.path = testDetailsPath
        testComposer.details.group = testDetailsGroup
        testComposer.details.perms = testDetailsPerms

        testDir = os.getcwd()

        testComposer.write()

        self.assertTrue(testDetailsPath.exists())

        with testDetailsPath.open() as testFile:
            testLines = testFile.readlines()

        for i in range(0, len(testLines)):
            testLines[i] = testLines[i].strip()

        self.assertEqual(testLines[0], "#!/usr/env/python")
        self.assertEqual(testLines[1], "# -G pam")
        self.assertEqual(testLines[2], "# -N fam")
        self.assertEqual(testLines[3], "")
        self.assertEqual(testLines[4], "")

        self.assertEqual(len(testLines), 5)

        testStat = testDetailsPath.stat()
        expectedStat=stat.S_IFREG + stat.S_IRWXU + stat.S_IRGRP + stat.S_IWGRP

        self.assertEqual(testStat.st_mode, expectedStat)

        testGID = testStat.st_gid

        testGID = grp.getgrgid(testGID).gr_name

        self.assertEqual(testGID, testDetailsGroup)

        testDetailsPath.unlink()
