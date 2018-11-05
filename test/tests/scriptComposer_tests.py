from __future__ import print_function, unicode_literals, division
import grp, os, pwd, stat, sys, unittest
from collections import OrderedDict

package_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(os.path.join(package_root, 'lib'))
sys.path.append(os.path.join(package_root, 'lib', 'pavilion', 'dependencies'))

from pavilion import scriptcomposer

class TestConfig( unittest.TestCase ):

    script_path = 'testName.batch'

    def setUp(self):
        """Set up for the scriptComposer tests."""
        if os.path.exists(self.script_path):
            print( "\nRemoving scriptfile {} from old (failed) run.".format(
                   self.script_path ), file=sys.stderr )
            os.remove(self.script_path)

    def test_header( self ):
        """Test for the scriptHeader class."""
        testHeader = scriptcomposer.scriptHeader()

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

        self.assertEqual( scriptcomposer.scriptHeader().shell_path,
                          testHeader.shell_path )
        self.assertEqual( scriptcomposer.scriptHeader().scheduler_macros,
                          testHeader.scheduler_macros )
        self.assertIsNone( testHeader.shell_path )
        self.assertIsNone( testHeader.scheduler_macros )

        # Testing initialization assignment.
        testPath = "/usr/env/python"
        testSched = OrderedDict()
        testSched[ "-g" ] = "9"
        testSched[ "-m" ] = "testThing"

        testHeader = scriptcomposer.scriptHeader( shell_path=testPath,
                                                  scheduler_macros=testSched )

        self.assertEqual( testHeader.shell_path, testPath )
        self.assertEqual( testHeader.scheduler_macros, testSched )

        testHeader.reset()

        # Testing invalid use cases.
        with self.assertRaises( TypeError ):
            testHeader.shell_path = 7

        with self.assertRaises( TypeError ):
            testHeader.scheduler_macros = [ '-G 12', '-L testThing' ]

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.scriptHeader( shell_path=7,
                                                     scheduler_macros=testSched
                                                    )

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.scriptHeader( shell_path=testPath,
                                                      scheduler_macros=[
                                                    '-G 12', '-L testThing' ] )

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.scriptHeader( shell_path=12,
                                                      scheduler_macros=13 )

    def test_modules( self ):
        """Test for the scriptModules class."""
        testModules = scriptcomposer.scriptModules()

        # Testing valid use cases.

        # Testing initialization
        self.assertIsNone( testModules.explicit_specification )
        self.assertFalse( testModules.purge )
        self.assertIsNone( testModules.swaps )
        self.assertIsNone( testModules.unloads )
        self.assertIsNone( testModules.loads )

        # Testing individual assignment.
        testExplicit = [ 'module load doodle',
                         'module unload puddle',
                         'module swap noodle poodle'
                         'module load oodle' ]

        testModules.explicit_specification = testExplicit

        self.assertEqual( testModules.explicit_specification, testExplicit )

        testPurge = True

        testModules.purge = testPurge

        self.assertTrue( testModules.purge )

        testSwaps = OrderedDict()
        testSwaps[ 'gcc' ] = 'intel'
        testSwaps[ 'openmpi' ] = 'mvapich2/some-version'

        testModules.swaps = testSwaps

        self.assertEqual( testModules.swaps, testSwaps )

        testUnloads = [ 'gcc', 'openmpi', 'python' ]

        testModules.unloads = testUnloads

        self.assertEqual( testModules.unloads, testUnloads )

        testLoads = [ 'intel', 'mvapich2', 'qt' ]

        testModules.loads = testLoads

        self.assertEqual( testModules.loads, testLoads )

        # Testing reset.
        testModules.reset()

        self.assertIsNone( testModules.explicit_specification )
        self.assertFalse( testModules.purge )
        self.assertIsNone( testModules.swaps )
        self.assertIsNone( testModules.unloads )
        self.assertIsNone( testModules.loads )

        # Testing init specification.
        # Start with use-case #1 where just the explicit specification is given
        testModules = scriptcomposer.scriptModules(
                                          explicit_specification=testExplicit )

        self.assertEqual( testModules.explicit_specification, testExplicit )
        self.assertFalse( testModules.purge )
        self.assertIsNone( testModules.swaps )
        self.assertIsNone( testModules.unloads )
        self.assertIsNone( testModules.loads )

        # Use-case #2 where everything but the explicit specification is given.
        testModules = scriptcomposer.scriptModules( purge=testPurge,
                                                    swaps=testSwaps,
                                                    unloads=testUnloads,
                                                    loads=testLoads )

        self.assertIsNone( testModules.explicit_specification )
        self.assertTrue( testModules.purge )
        self.assertEqual( testModules.swaps, testSwaps )
        self.assertEqual( testModules.unloads, testUnloads )
        self.assertEqual( testModules.loads, testLoads )

        testModules.reset()

        # Testing failure modes.
        with self.assertRaises( TypeError ):
            testModules.explicit_specification = { 'test': 'failure' }

        with self.assertRaises( TypeError ):
            testModules.purge = 'failure'

        with self.assertRaises( TypeError ):
            testModules.swaps = [ 'wrong' ]

        with self.assertRaises( TypeError ):
            testModules.unloads = 7

        with self.assertRaises( TypeError ):
            testModules.loads = True

        with self.assertRaises( TypeError ):
            testModules = scriptcomposer.scriptModules(
                                 explicit_specification={ 'test': 'failure' } )

        with self.assertRaises( TypeError ):
            testModules = scriptcomposer.scriptModules( purge='failure',
                                                        swaps=[ 'wrong' ],
                                                        unloads=7,
                                                        loads=True )


    def test_environment( self ):
        """Testing the scriptEnvironment class."""

        testSets = OrderedDict()
        testSets[ 'key1' ] = 'val1'
        testSets[ 'key2' ] = 'val2'

        testUnsets = [ 'test1', 'test2', 'test3' ]

        # Testing valid uses.

        # Testing initialization and defaults.
        testEnvironment = scriptcomposer.scriptEnvironment()

        self.assertIsNone( testEnvironment.sets )
        self.assertIsNone( testEnvironment.unsets )

        # Testing individual setting of variables.
        testEnvironment.sets = testSets
        testEnvironment.unsets = testUnsets

        self.assertEqual( testEnvironment.sets, testSets )
        self.assertEqual( testEnvironment.unsets, testUnsets )

        # Testing value reset.
        testEnvironment.reset()

        self.assertIsNone( testEnvironment.sets )
        self.assertIsNone( testEnvironment.unsets )

        # Testing initialization assignment.
        testEnvironment = scriptcomposer.scriptEnvironment( sets=testSets,
                                                            unsets=testUnsets )

        self.assertEqual( testEnvironment.sets, testSets )
        self.assertEqual( testEnvironment.unsets, testUnsets )

        testEnvironment.reset()

        # Testing invalid uses.
        with self.assertRaises( TypeError ):
            testEnvironment.sets = testUnsets

        with self.assertRaises( TypeError ):
            testEnvironment.unsets = testSets

        with self.assertRaises( TypeError ):
            testEnvironment = scriptcomposer.scriptEnvironment(sets=testUnsets,
                                                               unsets=testSets)


    def test_commands( self ):
        """Testing the scriptCommands class."""

        testCommands = [ './run_test_prolog',
                         './run_test -with -options testname',
                         './run_test_prolog' ]

        # Testing valid uses.
        # Testing initialization and defaults.
        testCommand = scriptcomposer.scriptCommands()

        self.assertIsNone( testCommand.commands )

        # Testing individual assignment.
        testCommand.commands = testCommands

        self.assertEqual( testCommand.commands, testCommands )

        # Testing reset.
        testCommand.reset()

        self.assertIsNone( testCommand.commands )

        # Testing initialization assignment.
        testCommand = scriptcomposer.scriptCommands( commands=testCommands )

        self.assertEqual( testCommand.commands, testCommands )

        testCommand.reset()

        # Testing invalid uses.
        with self.assertRaises( TypeError ):
            testCommand.commands = 87

        with self.assertRaises( TypeError ):
            testCommand = scriptcomposer.scriptCommands( commands=True )


    def test_post( self ):
        """Testing the scriptPost class."""

        testCommands = [ './post_test_prolog',
                         './post_test -with -options testname',
                         './post_test_prolog' ]

        # Testing valid uses.
        # Testing initialization and defaults.
        testPost = scriptcomposer.scriptPost()

        self.assertIsNone( testPost.commands )

        # Testing individual assignment.
        testPost.commands = testCommands

        self.assertEqual( testPost.commands, testCommands )

        # Testing reset.
        testPost.reset()

        self.assertIsNone( testPost.commands )

        # Testing initialization assignment.
        testPost = scriptcomposer.scriptPost( commands=testCommands )

        self.assertEqual( testPost.commands, testCommands )

        testPost.reset()

        # Testing invalid uses.
        with self.assertRaises( TypeError ):
            testPost.commands = 87

        with self.assertRaises( TypeError ):
            testPost = scriptcomposer.scriptPost( commands=True )


    def test_details( self ):
        """Testing the scriptDetails class."""

        testName = 'testScript.sh'

        testType = 'bash'

        testUser = 'tank'

        testGroup = 'anonymous'

        testOP = 5
        testGP = 3
        testWP = 1

        # Testing valid uses.

        # Testing initialization and defaults.
        testDetails = scriptcomposer.scriptDetails()

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
        testDetails = scriptcomposer.scriptDetails( name=testName,
                                                    script_type=testType,
                                                    user=testUser,
                                                    group=testGroup,
                                                    owner_perms=testOP,
                                                    group_perms=testGP,
                                                    world_perms=testWP )

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
            testDetails = scriptcomposer.scriptDetails( name=testName,
                                                        script_type=testType,
                                                        user=testUser,
                                                        group=testGroup,
                                                        owner_perms=7,
                                                        group_perms=7,
                                                        world_perms=u'fail' )


    def test_scriptComposer( self ):
        """Testing scriptComposer class variable setting."""

        # Testing valid uses.

        # Testing initialization defaults.
        testComposer = scriptcomposer.scriptComposer()

        self.assertIsInstance( testComposer.header,
                                     scriptcomposer.scriptHeader )
        self.assertIsInstance( testComposer.modules,
                                     scriptcomposer.scriptModules )
        self.assertIsInstance( testComposer.environment,
                                     scriptcomposer.scriptEnvironment )
        self.assertIsInstance( testComposer.commands,
                                     scriptcomposer.scriptCommands )
        self.assertIsInstance( testComposer.post, scriptcomposer.scriptPost )
        self.assertIsInstance( testComposer.details,
                                     scriptcomposer.scriptDetails )

        self.assertIsNone( testComposer.header.shell_path )
        self.assertIsNone( testComposer.header.scheduler_macros )

        self.assertIsNone( testComposer.modules.explicit_specification )
        self.assertFalse( testComposer.modules.purge )
        self.assertIsNone( testComposer.modules.swaps )
        self.assertIsNone( testComposer.modules.unloads )
        self.assertIsNone( testComposer.modules.loads )

        self.assertIsNone( testComposer.environment.unsets )
        self.assertIsNone( testComposer.environment.sets )

        self.assertIsNone( testComposer.commands.commands )

        self.assertIsNone( testComposer.post.commands )

        self.assertEqual( testComposer.details.script_type, "bash" )
        self.assertEqual( testComposer.details.user, os.environ['USER'] )
        self.assertEqual( testComposer.details.group, os.environ['USER'] )
        self.assertEqual( testComposer.details.owner_perms, 7 )
        self.assertEqual( testComposer.details.group_perms, 5 )
        self.assertEqual( testComposer.details.world_perms, 0 )

        # Testing individual assignment
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler[ '-G' ] = 'pam'
        testHeaderScheduler[ '-N' ] = 'fam'

        testModulesExplicit = [ 'taco', 'burrito', 'nachos' ]
        testModulesPurge = True
        testModulesSwaps = OrderedDict()
        testModulesSwaps[ 'taco' ] = 'spaghetti'
        testModulesSwaps[ 'burrito' ] = 'lasagna'
        testModulesSwaps[ 'nachos' ] = 'ravioli'
        testModulesUnloads = [ 'salmon', 'bass', 'tuna' ]
        testModulesLoads = [ 'brownies', 'cookies', 'cake' ]

        testEnvUnsets = [ 'useless', 'unwanted', 'undesired' ]
        testEnvSets = OrderedDict()
        testEnvSets[ 'new' ] = 'hotness'
        testEnvSets[ 'hot' ] = 'newness'

        testCommands = [ 'do', 'the', 'thing' ]

        testPost = [ 'thing', 'was', 'done' ]

        testDetailsName = 'testName'
        testDetailsType = 'batch'
        testDetailsUser = 'me'
        testDetailsGroup = 'groupies'
        testDetailsOP = 1
        testDetailsGP = 2
        testDetailsWP = 3

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_macros = testHeaderScheduler

        testComposer.modules.explicit_specification = testModulesExplicit
        testComposer.modules.purge = testModulesPurge
        testComposer.modules.swaps = testModulesSwaps
        testComposer.modules.unloads = testModulesUnloads
        testComposer.modules.loads = testModulesLoads

        testComposer.environment.unsets = testEnvUnsets
        testComposer.environment.sets = testEnvSets

        testComposer.commands.commands = testCommands

        testComposer.post.commands = testPost

        testComposer.details.name = testDetailsName
        testComposer.details.script_type = testDetailsType
        testComposer.details.user = testDetailsUser
        testComposer.details.group = testDetailsGroup
        testComposer.details.owner_perms = testDetailsOP
        testComposer.details.group_perms = testDetailsGP
        testComposer.details.world_perms = testDetailsWP

        self.assertEqual( testComposer.header.shell_path, testHeaderShell )
        self.assertEqual( testComposer.header.scheduler_macros,
                                                          testHeaderScheduler )

        self.assertEqual( testComposer.modules.explicit_specification,
                                                          testModulesExplicit )
        self.assertTrue( testComposer.modules.purge )
        self.assertEqual( testComposer.modules.swaps, testModulesSwaps )
        self.assertEqual( testComposer.modules.unloads, testModulesUnloads )
        self.assertEqual( testComposer.modules.loads, testModulesLoads )

        self.assertEqual( testComposer.environment.unsets, testEnvUnsets )
        self.assertEqual( testComposer.environment.sets, testEnvSets )

        self.assertEqual( testComposer.commands.commands, testCommands )

        self.assertEqual( testComposer.post.commands, testPost )

        self.assertEqual( testComposer.details.name, testDetailsName )
        self.assertEqual( testComposer.details.script_type, testDetailsType )
        self.assertEqual( testComposer.details.user, testDetailsUser )
        self.assertEqual( testComposer.details.group, testDetailsGroup )
        self.assertEqual( testComposer.details.owner_perms, testDetailsOP )
        self.assertEqual( testComposer.details.group_perms, testDetailsGP )
        self.assertEqual( testComposer.details.world_perms, testDetailsWP )

        # Testing reset.
        testComposer.reset()

        self.assertIsNone( testComposer.header.shell_path )
        self.assertIsNone( testComposer.header.scheduler_macros )

        self.assertIsNone( testComposer.modules.explicit_specification )
        self.assertFalse( testComposer.modules.purge )
        self.assertIsNone( testComposer.modules.swaps )
        self.assertIsNone( testComposer.modules.unloads )
        self.assertIsNone( testComposer.modules.loads )

        self.assertIsNone( testComposer.environment.unsets )
        self.assertIsNone( testComposer.environment.sets )

        self.assertIsNone( testComposer.commands.commands )

        self.assertIsNone( testComposer.post.commands )

        self.assertEqual( testComposer.details.script_type, "bash" )
        self.assertEqual( testComposer.details.user, os.environ['USER'] )
        self.assertEqual( testComposer.details.group, os.environ['USER'] )
        self.assertEqual( testComposer.details.owner_perms, 7 )
        self.assertEqual( testComposer.details.group_perms, 5 )
        self.assertEqual( testComposer.details.world_perms, 0 )

        # Testing object assignment.
        testHeaderObj = scriptcomposer.scriptHeader(shell_path=testHeaderShell,
                                                    scheduler_macros=
                                                           testHeaderScheduler)

        testModulesObj = scriptcomposer.scriptModules( explicit_specification=
                                                           testModulesExplicit,
                                                      purge=testModulesPurge,
                                                      swaps=testModulesSwaps,
                                                      unloads=
                                                            testModulesUnloads,
                                                      loads=testModulesLoads )

        testEnvObj = scriptcomposer.scriptEnvironment( sets=testEnvSets,
                                                       unsets=testEnvUnsets )

        testCommandObj = scriptcomposer.scriptCommands( commands=testCommands )

        testPostObj = scriptcomposer.scriptPost( commands=testPost )

        testDetailsObj = scriptcomposer.scriptDetails( name=testDetailsName,
                                                       script_type=
                                                               testDetailsType,
                                                       user=testDetailsUser,
                                                       group=testDetailsGroup,
                                                       owner_perms=
                                                                 testDetailsOP,
                                                       group_perms=
                                                                 testDetailsGP,
                                                       world_perms=
                                                                testDetailsWP )

        testComposer.header = testHeaderObj
        testComposer.modules = testModulesObj
        testComposer.environment = testEnvObj
        testComposer.commands = testCommandObj
        testComposer.post = testPostObj
        testComposer.details = testDetailsObj

        self.assertEqual( testComposer.header.shell_path, testHeaderShell )
        self.assertEqual( testComposer.header.scheduler_macros,
                                                          testHeaderScheduler )

        self.assertEqual( testComposer.modules.explicit_specification,
                                                          testModulesExplicit )
        self.assertTrue( testComposer.modules.purge )
        self.assertEqual( testComposer.modules.swaps, testModulesSwaps )
        self.assertEqual( testComposer.modules.unloads, testModulesUnloads )
        self.assertEqual( testComposer.modules.loads, testModulesLoads )

        self.assertEqual( testComposer.environment.unsets, testEnvUnsets )
        self.assertEqual( testComposer.environment.sets, testEnvSets )

        self.assertEqual( testComposer.commands.commands, testCommands )

        self.assertEqual( testComposer.post.commands, testPost )

        self.assertEqual( testComposer.details.name, testDetailsName )
        self.assertEqual( testComposer.details.script_type, testDetailsType )
        self.assertEqual( testComposer.details.user, testDetailsUser )
        self.assertEqual( testComposer.details.group, testDetailsGroup )
        self.assertEqual( testComposer.details.owner_perms, testDetailsOP )
        self.assertEqual( testComposer.details.group_perms, testDetailsGP )
        self.assertEqual( testComposer.details.world_perms, testDetailsWP )


    def test_writeScript( self ):
        """Testing the writeScript function of the scriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler[ '-G' ] = 'pam'
        testHeaderScheduler[ '-N' ] = 'fam'

        testModulesExplicit = [ 'taco', 'burrito', 'nachos' ]
        testModulesPurge = True
        testModulesSwaps = OrderedDict()
        testModulesSwaps[ 'taco' ] = 'spaghetti'
        testModulesSwaps[ 'burrito' ] = 'lasagna'
        testModulesSwaps[ 'nachos' ] = 'ravioli'
        testModulesUnloads = [ 'salmon', 'bass', 'tuna' ]
        testModulesLoads = [ 'brownies', 'cookies', 'cake' ]

        testEnvUnsets = [ 'useless', 'unwanted', 'undesired' ]
        testEnvSets = OrderedDict()
        testEnvSets[ 'new' ] = 'hotness'
        testEnvSets[ 'hot' ] = 'newness'

        testCommands = [ 'do', 'the', 'thing' ]

        testPost = [ 'thing', 'was', 'done' ]

        testDetailsName = 'testName'
        testDetailsType = 'batch'
        testDetailsUser = os.environ['USER'].decode()
        testDetailsGroup = 'gzshared'
        testDetailsOP = 7
        testDetailsGP = 6
        testDetailsWP = 0

        testComposer = scriptcomposer.scriptComposer()

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_macros = testHeaderScheduler

        testComposer.modules.explicit_specification = testModulesExplicit
        testComposer.modules.purge = testModulesPurge
        testComposer.modules.swaps = testModulesSwaps
        testComposer.modules.unloads = testModulesUnloads
        testComposer.modules.loads = testModulesLoads

        testComposer.environment.unsets = testEnvUnsets
        testComposer.environment.sets = testEnvSets

        testComposer.commands.commands = testCommands

        testComposer.post.commands = testPost

        testComposer.details.name = testDetailsName
        testComposer.details.script_type = testDetailsType
        testComposer.details.user = testDetailsUser
        testComposer.details.group = testDetailsGroup
        testComposer.details.owner_perms = testDetailsOP
        testComposer.details.group_perms = testDetailsGP
        testComposer.details.world_perms = testDetailsWP

        testDir = os.getcwd()

        testComposer.writeScript( testDir )

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

        self.assertEqual( testLines[4], "taco" )
        self.assertEqual( testLines[5], "burrito" )
        self.assertEqual( testLines[6], "nachos" )

        self.assertEqual( testLines[7], "" )

        self.assertEqual( testLines[8], "unset useless" )
        self.assertEqual( testLines[9], "unset unwanted" )
        self.assertEqual( testLines[10], "unset undesired" )
        self.assertEqual( testLines[11], "export new=hotness" )
        self.assertEqual( testLines[12], "export hot=newness" )

        self.assertEqual( testLines[13], "" )

        self.assertEqual( testLines[14], "do" )
        self.assertEqual( testLines[15], "the" )
        self.assertEqual( testLines[16], "thing" )

        self.assertEqual( testLines[17], "" )

        self.assertEqual( testLines[18], "thing" )
        self.assertEqual( testLines[19], "was" )
        self.assertEqual( testLines[20], "done" )

        self.assertEqual( len(testLines), 21 )

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


    def test_writeScript_2( self ):
        """Testing the writeScript function of the scriptComposer class."""
        testHeaderShell = "/usr/env/python"
        testHeaderScheduler = OrderedDict()
        testHeaderScheduler[ '-G' ] = 'pam'
        testHeaderScheduler[ '-N' ] = 'fam'

        testModulesPurge = True
        testModulesSwaps = OrderedDict()
        testModulesSwaps[ 'taco' ] = 'spaghetti'
        testModulesSwaps[ 'burrito' ] = 'lasagna'
        testModulesSwaps[ 'nachos' ] = 'ravioli'
        testModulesUnloads = [ 'salmon', 'bass', 'tuna' ]
        testModulesLoads = [ 'brownies', 'cookies', 'cake' ]

        testEnvUnsets = [ 'useless', 'unwanted', 'undesired' ]
        testEnvSets = OrderedDict()
        testEnvSets[ 'new' ] = 'hotness'
        testEnvSets[ 'hot' ] = 'newness'

        testCommands = [ 'do', 'the', 'thing' ]

        testPost = [ 'thing', 'was', 'done' ]

        testDetailsName = 'testName'
        testDetailsType = 'batch'
        testDetailsUser = os.environ['USER'].decode()
        testDetailsGroup = 'gzshared'
        testDetailsOP = 7
        testDetailsGP = 6
        testDetailsWP = 0

        testComposer = scriptcomposer.scriptComposer()

        testComposer.header.shell_path = testHeaderShell
        testComposer.header.scheduler_macros = testHeaderScheduler

        testComposer.modules.purge = testModulesPurge
        testComposer.modules.swaps = testModulesSwaps
        testComposer.modules.unloads = testModulesUnloads
        testComposer.modules.loads = testModulesLoads

        testComposer.environment.unsets = testEnvUnsets
        testComposer.environment.sets = testEnvSets

        testComposer.commands.commands = testCommands

        testComposer.post.commands = testPost

        testComposer.details.name = testDetailsName
        testComposer.details.script_type = testDetailsType
        testComposer.details.user = testDetailsUser
        testComposer.details.group = testDetailsGroup
        testComposer.details.owner_perms = testDetailsOP
        testComposer.details.group_perms = testDetailsGP
        testComposer.details.world_perms = testDetailsWP

        testDir = os.getcwd()

        testComposer.writeScript( testDir )

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

        self.assertEqual( testLines[4], "module purge" )
        self.assertEqual( testLines[5], "module swap taco spaghetti" )
        self.assertEqual( testLines[6], "module swap burrito lasagna" )
        self.assertEqual( testLines[7], "module swap nachos ravioli" )
        self.assertEqual( testLines[8], "module unload salmon" )
        self.assertEqual( testLines[9], "module unload bass" )
        self.assertEqual( testLines[10], "module unload tuna" )
        self.assertEqual( testLines[11], "module load brownies" )
        self.assertEqual( testLines[12], "module load cookies" )
        self.assertEqual( testLines[13], "module load cake" )

        self.assertEqual( testLines[14], "" )

        self.assertEqual( testLines[15], "unset useless" )
        self.assertEqual( testLines[16], "unset unwanted" )
        self.assertEqual( testLines[17], "unset undesired" )
        self.assertEqual( testLines[18], "export new=hotness" )
        self.assertEqual( testLines[19], "export hot=newness" )

        self.assertEqual( testLines[20], "" )

        self.assertEqual( testLines[21], "do" )
        self.assertEqual( testLines[22], "the" )
        self.assertEqual( testLines[23], "thing" )

        self.assertEqual( testLines[24], "" )

        self.assertEqual( testLines[25], "thing" )
        self.assertEqual( testLines[26], "was" )
        self.assertEqual( testLines[27], "done" )

        self.assertEqual( len(testLines), 28 )

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
