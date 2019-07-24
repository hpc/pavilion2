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
            shell_path="#!/bin/sh",
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
        testDetails = scriptcomposer.ScriptDetails()

        self.assertEqual(testDetails.group, utils.get_login())
        self.assertEqual(testDetails.perms, oct(0o770))

        # Testing individual assignment.
        testDetails.path = testPath
        testDetails.group = testGroup
        testDetails.perms = testPerms

        self.assertEqual(testDetails.path, Path(testPath))
        self.assertEqual(testDetails.group, testGroup)
        self.assertEqual(testDetails.perms, oct(testPerms))

        # Testing reset.
        testDetails.reset()

        self.assertEqual(testDetails.group, utils.get_login())
        self.assertEqual(testDetails.perms, oct(0o770))

        # Testing initialization assignment.
        testDetails = scriptcomposer.ScriptDetails(path=testPath,
                                                   group=testGroup,
                                                   perms=testPerms)

        self.assertEqual(testDetails.path, Path(testPath))
        self.assertEqual(testDetails.group, testGroup)
        self.assertEqual(testDetails.perms, oct(testPerms))

        testDetails.reset()

        # Testing invalid uses.
        with self.assertRaises(TypeError):
            testDetails.path = True

        with self.assertRaises(TypeError):
            testDetails.perms = 'string'

        with self.assertRaises(TypeError):
            testDetails.perms = u'fail'

        with self.assertRaises(TypeError):
            testDetails.perms = 7.5

        # Testing invalid initialization.
        with self.assertRaises(TypeError):
            testDetails = scriptcomposer.ScriptDetails(path=testPath,
                                                       group=testGroup,
                                                       perms=u'fail')

    def test_scriptComposer(self):
        """Testing ScriptComposer class variable setting."""

        # Testing valid uses.

        # Testing initialization defaults.
        testComposer = scriptcomposer.ScriptComposer()

        self.assertIsInstance(testComposer.header,
                              scriptcomposer.ScriptHeader)
        self.assertIsInstance(testComposer.details,
                              scriptcomposer.ScriptDetails)

        self.assertEqual(testComposer.header.shell_path, '#!/bin/bash')
        self.assertEqual(testComposer.header.scheduler_headers, [])

        self.assertEqual(testComposer.details.group, utils.get_login())
        self.assertEqual(testComposer.details.perms, oct(0o770))

        # Testing individual assignment
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler['-G'] = 'pam'
        testHeaderScheduler['-N'] = 'fam'

        testComposer.newline()

        testComposer.command(['taco', 'burrito', 'nachos'])

        testDetailsPath = 'testPath'
        testDetailsGroup = 'groupies'
        testDetailsPerms = 0o543

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_headers = testHeaderScheduler

        testComposer.details.path = testDetailsPath
        testComposer.details.group = testDetailsGroup
        testComposer.details.perms = testDetailsPerms

        self.assertEqual(testComposer.header.shell_path, testHeaderShell)
        self.assertEqual(testComposer.header.scheduler_headers,
                                                          testHeaderScheduler)

        self.assertEqual(testComposer.details.path, Path(testDetailsPath))
        self.assertEqual(testComposer.details.group, testDetailsGroup)
        self.assertEqual(testComposer.details.perms, oct(testDetailsPerms))

        # Testing reset.
        testComposer.reset()

        self.assertEqual(testComposer.header.shell_path, '#!/bin/bash')
        self.assertEqual(testComposer.header.scheduler_headers, [])

        self.assertEqual(testComposer.details.group, utils.get_login())
        self.assertEqual(testComposer.details.perms, oct(0o770))

        # Testing object assignment.
        testHeaderObj = scriptcomposer.ScriptHeader(shell_path=testHeaderShell,
            scheduler_headers=testHeaderScheduler)

        testDetailsObj = scriptcomposer.ScriptDetails(path=testDetailsPath,
            group = testDetailsGroup, perms = testDetailsPerms)

        testComposer.header = testHeaderObj
        testComposer.details = testDetailsObj

        self.assertEqual(testComposer.header.shell_path, testHeaderShell)
        self.assertEqual(testComposer.header.scheduler_headers,
                                                          testHeaderScheduler)

        self.assertEqual(testComposer.details.path, Path(testDetailsPath))
        self.assertEqual(testComposer.details.group, testDetailsGroup)
        self.assertEqual(testComposer.details.perms, oct(testDetailsPerms))


    def test_writeScript(self):
        """Testing the writeScript function of the ScriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = ['-G pam', '-N fam']

        testDetailsPath = self.pav_cfg.working_dir/'testPath'
        testDetailsGroup = self._other_group()
        testDetailsPerms = 0o760

        testComposer = scriptcomposer.ScriptComposer()

        testComposer.header.shell_path = testHeaderShell
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
