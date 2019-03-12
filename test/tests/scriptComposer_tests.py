import grp, os, pwd, stat, sys, unittest
from collections import OrderedDict

package_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(os.path.join(package_root, 'lib'))
sys.path.append(os.path.join(package_root, 'lib', 'pavilion', 'dependencies'))

from pavilion import scriptcomposer

class TestConfig( unittest.TestCase ):

    script_path = 'testName.batch'

    def setUp(self):
        """Set up for the ScriptComposer tests."""
        if os.path.exists(self.script_path):
            print( "\nRemoving scriptfile {} from old (failed) run.".format(
                   self.script_path ), file=sys.stderr )
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

    @unittest.skip
    def test_header( self ):
        """Test for the ScriptHeader class."""
        testHeader = scriptcomposer.ScriptHeader()

        # Testing valid use cases.

        # Testing initialization.
        self.assertIsNone( testHeader.shell_path )
        self.assertIsNone( testHeader.scheduler_macros )

        # Testing individual assignment.
        testPath = "/bin/bash"

        testHeader.shell_path = testPath

        self.assertEqual( testHeader.shell_path, testPath )

        testSched = OrderedDict()
        testSched[ '-G' ] = "12"
        testSched[ '-L' ] = "testThing"

        testHeader.scheduler_macros = testSched

        self.assertEqual( testHeader.scheduler_macros, testSched )

        # Testing reset functionality.
        testHeader.reset()

        self.assertEqual(scriptcomposer.ScriptHeader().shell_path,
                         testHeader.shell_path)
        self.assertEqual(scriptcomposer.ScriptHeader().scheduler_macros,
                         testHeader.scheduler_macros)
        self.assertIsNone( testHeader.shell_path )
        self.assertIsNone( testHeader.scheduler_macros )

        # Testing initialization assignment.
        testPath = "/usr/env/python"
        testSched = OrderedDict()
        testSched[ "-g" ] = "9"
        testSched[ "-m" ] = "testThing"

        testHeader = scriptcomposer.ScriptHeader(shell_path=testPath,
                                                 scheduler_macros=testSched)

        self.assertEqual( testHeader.shell_path, testPath )
        self.assertEqual( testHeader.scheduler_macros, testSched )

        testHeader.reset()

        # Testing invalid use cases.
        with self.assertRaises( TypeError ):
            testHeader.shell_path = 7

        with self.assertRaises( TypeError ):
            testHeader.scheduler_macros = [ '-G 12', '-L testThing' ]

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.ScriptHeader(shell_path=7,
                                                     scheduler_macros=testSched
                                                     )

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.ScriptHeader(shell_path=testPath,
                                                     scheduler_macros=[
                                                    '-G 12', '-L testThing' ])

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.ScriptHeader(shell_path=12,
                                                     scheduler_macros=13)

    @unittest.skip
    def test_details( self ):
        """Testing the ScriptBody class."""

        testName = 'testScript.sh'

        testType = 'bash'

        testUser = 'tank'

        testGroup = 'anonymous'

        testOP = 5
        testGP = 3
        testWP = 1

        # Testing valid uses.

        # Testing initialization and defaults.
        testDetails = scriptcomposer.ScriptBody()

        self.assertEqual( testDetails.script_type, "bash" )
        self.assertEqual( testDetails.user, os.environ['USER'] )
        self.assertEqual( testDetails.group, os.environ['USER'] )
        self.assertEqual( testDetails.owner_perms, 7 )
        self.assertEqual( testDetails.group_perms, 5 )
        self.assertEqual( testDetails.world_perms, 0 )

        # Testing individual assignment.
        testDetails.name = testName
        testDetails.script_type = testType
        testDetails.user = testUser
        testDetails.group = testGroup
        testDetails.owner_perms = testOP
        testDetails.group_perms = testGP
        testDetails.world_perms = testWP

        self.assertEqual( testDetails.name, testName )
        self.assertEqual( testDetails.script_type, testType )
        self.assertEqual( testDetails.user, testUser )
        self.assertEqual( testDetails.group, testGroup )
        self.assertEqual( testDetails.owner_perms, testOP )
        self.assertEqual( testDetails.group_perms, testGP )
        self.assertEqual( testDetails.world_perms, testWP )

        # Testing reset.
        testDetails.reset()

        self.assertEqual( testDetails.script_type, "bash" )
        self.assertEqual( testDetails.user, os.environ['USER'] )
        self.assertEqual( testDetails.group, os.environ['USER'] )
        self.assertEqual( testDetails.owner_perms, 7 )
        self.assertEqual( testDetails.group_perms, 5 )
        self.assertEqual( testDetails.world_perms, 0 )

        # Testing initialization assignment.
        testDetails = scriptcomposer.ScriptBody(name=testName,
                                                script_type=testType,
                                                user=testUser,
                                                group=testGroup,
                                                owner_perms=testOP,
                                                group_perms=testGP,
                                                world_perms=testWP)

        self.assertEqual( testDetails.name, testName )
        self.assertEqual( testDetails.script_type, testType )
        self.assertEqual( testDetails.user, testUser )
        self.assertEqual( testDetails.group, testGroup )
        self.assertEqual( testDetails.owner_perms, testOP )
        self.assertEqual( testDetails.group_perms, testGP )
        self.assertEqual( testDetails.world_perms, testWP )

        testDetails.reset()

        # Testing invalid uses.
        with self.assertRaises( TypeError ):
            testDetails.name = True

        with self.assertRaises( TypeError ):
            testDetails.script_type = 7

        with self.assertRaises( TypeError ):
            testDetails.user = [ 'name' ]

        with self.assertRaises( TypeError ):
            testDetails.group = { 'group': 'fail' }

        with self.assertRaises( TypeError ):
            testDetails.owner_perms = 'string'

        with self.assertRaises( TypeError ):
            testDetails.group_perms = u'fail'

        with self.assertRaises( TypeError ):
            testDetails.world_perms = 7.5

        with self.assertRaises( ValueError ):
            testDetails.owner_perms = 8

        with self.assertRaises( ValueError ):
            testDetails.group_perms = -1

        with self.assertRaises( ValueError ):
            testDetails.world_perms = 99

        # Testing invalid initialization.
        with self.assertRaises( TypeError ):
            testDetails = scriptcomposer.ScriptBody(name=testName,
                                                    script_type=testType,
                                                    user=testUser,
                                                    group=testGroup,
                                                    owner_perms=7,
                                                    group_perms=7,
                                                    world_perms=u'fail')

    @unittest.skip
    def test_scriptComposer( self ):
        """Testing ScriptComposer class variable setting."""

        # Testing valid uses.

        # Testing initialization defaults.
        testComposer = scriptcomposer.ScriptComposer()

        self.assertIsInstance(testComposer.header,
                              scriptcomposer.ScriptHeader)
        self.assertIsInstance(testComposer.body,
                              scriptcomposer.ScriptBody)

        self.assertIsNone( testComposer.header.shell_path )
        self.assertIsNone( testComposer.header.scheduler_macros )

        self.assertEqual(testComposer.body.script_type, "bash")
        self.assertEqual(testComposer.body.user, os.environ['USER'])
        self.assertEqual(testComposer.body.group, os.environ['USER'])
        self.assertEqual(testComposer.body.owner_perms, 7)
        self.assertEqual(testComposer.body.group_perms, 5)
        self.assertEqual(testComposer.body.world_perms, 0)

        # Testing individual assignment
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler[ '-G' ] = 'pam'
        testHeaderScheduler[ '-N' ] = 'fam'

        testComposer.newline()

        testComposer.command(['taco', 'burrito', 'nachos'])

        testDetailsName = 'testName'
        testDetailsType = 'batch'
        testDetailsUser = 'me'
        testDetailsGroup = 'groupies'
        testDetailsOP = 1
        testDetailsGP = 2
        testDetailsWP = 3

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_macros = testHeaderScheduler

        testComposer.body.name = testDetailsName
        testComposer.body.script_type = testDetailsType
        testComposer.body.user = testDetailsUser
        testComposer.body.group = testDetailsGroup
        testComposer.body.owner_perms = testDetailsOP
        testComposer.body.group_perms = testDetailsGP
        testComposer.body.world_perms = testDetailsWP

        self.assertEqual( testComposer.header.shell_path, testHeaderShell )
        self.assertEqual( testComposer.header.scheduler_macros,
                                                          testHeaderScheduler )

        self.assertEqual(testComposer.body.name, testDetailsName)
        self.assertEqual(testComposer.body.script_type, testDetailsType)
        self.assertEqual(testComposer.body.user, testDetailsUser)
        self.assertEqual(testComposer.body.group, testDetailsGroup)
        self.assertEqual(testComposer.body.owner_perms, testDetailsOP)
        self.assertEqual(testComposer.body.group_perms, testDetailsGP)
        self.assertEqual(testComposer.body.world_perms, testDetailsWP)

        # Testing reset.
        testComposer.reset()

        self.assertIsNone( testComposer.header.shell_path )
        self.assertIsNone( testComposer.header.scheduler_macros )

        self.assertEqual(testComposer.body.script_type, "bash")
        self.assertEqual(testComposer.body.user, os.environ['USER'])
        self.assertEqual(testComposer.body.group, os.environ['USER'])
        self.assertEqual(testComposer.body.owner_perms, 7)
        self.assertEqual(testComposer.body.group_perms, 5)
        self.assertEqual(testComposer.body.world_perms, 0)

        # Testing object assignment.
        testHeaderObj = scriptcomposer.ScriptHeader(shell_path=testHeaderShell,
                                                    scheduler_macros=
                                                           testHeaderScheduler)

        testDetailsObj = scriptcomposer.ScriptBody(name=testDetailsName,
                                                   script_type=
                                                               testDetailsType,
                                                   user=testDetailsUser,
                                                   group=testDetailsGroup,
                                                   owner_perms=
                                                                 testDetailsOP,
                                                   group_perms=
                                                                 testDetailsGP,
                                                   world_perms=
                                                                testDetailsWP)

        testComposer.header = testHeaderObj
        testComposer.body = testDetailsObj

        self.assertEqual( testComposer.header.shell_path, testHeaderShell )
        self.assertEqual( testComposer.header.scheduler_macros,
                                                          testHeaderScheduler )

        self.assertEqual(testComposer.body.name, testDetailsName)
        self.assertEqual(testComposer.body.script_type, testDetailsType)
        self.assertEqual(testComposer.body.user, testDetailsUser)
        self.assertEqual(testComposer.body.group, testDetailsGroup)
        self.assertEqual(testComposer.body.owner_perms, testDetailsOP)
        self.assertEqual(testComposer.body.group_perms, testDetailsGP)
        self.assertEqual(testComposer.body.world_perms, testDetailsWP)


    @unittest.skip
    def test_writeScript( self ):
        """Testing the writeScript function of the ScriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler[ '-G' ] = 'pam'
        testHeaderScheduler[ '-N' ] = 'fam'

        testDetailsName = 'testName'
        testDetailsType = 'batch'
        testDetailsUser = os.getlogin()
        testDetailsGroup = self._other_group()

        testDetailsOP = 7
        testDetailsGP = 6
        testDetailsWP = 0

        testComposer = scriptcomposer.ScriptComposer()

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_macros = testHeaderScheduler

        testComposer.body.name = testDetailsName
        testComposer.body.script_type = testDetailsType
        testComposer.body.user = testDetailsUser
        testComposer.body.group = testDetailsGroup
        testComposer.body.owner_perms = testDetailsOP
        testComposer.body.group_perms = testDetailsGP
        testComposer.body.world_perms = testDetailsWP

        testDir = os.getcwd()

        testComposer.write_script(testDir)

        self.assertTrue( os.path.isfile( os.path.join( testDir,
                                               testDetailsName + '.batch' ) ) )

        testFile = open(os.path.join( testDir, testDetailsName+'.batch'), 'r' )

        testLines = testFile.readlines()

        testFile.close()

        for i in range(0, len( testLines ) ):
            testLines[i] = testLines[i].strip()

        self.assertEqual( testLines[0], "#!/usr/env/python" )
        self.assertEqual( testLines[1], "# -G pam" )
        self.assertEqual( testLines[2], "# -N fam" )
        self.assertEqual( testLines[3], "" )

        self.assertEqual( len(testLines), 4 )

        testStat = os.stat( os.path.join(testDir, testDetailsName + '.batch') )
        expectedStat=stat.S_IFREG + stat.S_IRWXU + stat.S_IRGRP + stat.S_IWGRP

        self.assertEqual( testStat.st_mode, expectedStat )

        testUID = testStat.st_uid
        testGID = testStat.st_gid

        testUID = pwd.getpwuid( testUID ).pw_name
        testGID = grp.getgrgid( testGID ).gr_name

        self.assertEqual( testUID, testDetailsUser )
        self.assertEqual( testGID, testDetailsGroup )

        os.remove( os.path.join( testDir, testDetailsName + '.batch' ) )


    @unittest.skip
    def test_writeScript_2( self ):
        """Testing the writeScript function of the ScriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler[ '-G' ] = 'pam'
        testHeaderScheduler[ '-N' ] = 'fam'

        testDetailsName = 'testName'
        testDetailsType = 'batch'
        testDetailsUser = os.environ['USER']
        testDetailsGroup = self._other_group()
        testDetailsOP = 7
        testDetailsGP = 6
        testDetailsWP = 0

        testComposer = scriptcomposer.ScriptComposer()

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_macros = testHeaderScheduler

        testComposer.body.name = testDetailsName
        testComposer.body.script_type = testDetailsType
        testComposer.body.user = testDetailsUser
        testComposer.body.group = testDetailsGroup
        testComposer.body.owner_perms = testDetailsOP
        testComposer.body.group_perms = testDetailsGP
        testComposer.body.world_perms = testDetailsWP

        testDir = os.getcwd()

        testComposer.write_script(testDir)

        self.assertTrue( os.path.isfile( os.path.join( testDir,
                                               testDetailsName + '.batch' ) ) )

        testFile = open(os.path.join( testDir, testDetailsName+'.batch'), 'r' )

        testLines = testFile.readlines()

        testFile.close()

        for i in range(0, len( testLines ) ):
            testLines[i] = testLines[i].strip()

        self.assertEqual( testLines[0], "#!/usr/env/python" )
        self.assertEqual( testLines[1], "# -G pam" )
        self.assertEqual( testLines[2], "# -N fam" )
        self.assertEqual( testLines[3], "" )

        self.assertEqual( len(testLines), 4 )

        testStat = os.stat( os.path.join(testDir, testDetailsName + '.batch') )
        expectedStat=stat.S_IFREG + stat.S_IRWXU + stat.S_IRGRP + stat.S_IWGRP

        self.assertEqual( testStat.st_mode, expectedStat )

        testUID = testStat.st_uid
        testGID = testStat.st_gid

        testUID = pwd.getpwuid( testUID ).pw_name
        testGID = grp.getgrgid( testGID ).gr_name

        self.assertEqual( testUID, testDetailsUser )
        self.assertEqual( testGID, testDetailsGroup )

        os.remove( os.path.join( testDir, testDetailsName + '.batch' ) )
