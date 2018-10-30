from __future__ import print_function, unicode_literals, division
import os, sys, unittest

package_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(os.path.join(package_root, 'lib'))
sys.path.append(os.path.join(package_root, 'lib', 'pavilion', 'dependencies'))

from pavilion import scriptcomposer

class TestConfig( unittest.TestCase ):

#    script_path = 'scriptTest.sh'
#
#    def setUp(self):
#        """Set up for the scriptComposer tests."""
#        if os.path.exists(self.script_path):
#            print( "\nRemoving scriptfile {} from old (failed) run.".format(
#                   self.script_path ), file=sys.stderr )
#            os.remove(self.script_path)

    def test_header( self ):
        """Test for the scriptHeader class."""
        testHeader = scriptcomposer.scriptHeader()

        # Testing valid use cases.

        # Testing initialization.
        self.assertEqual( testHeader.shell_path, None )
        self.assertEqual( testHeader.scheduler_macros, None )

        # Testing individual assignment.
        testPath = "/bin/bash"

        testHeader.shell_path = testPath

        self.assertEqual( testHeader.shell_path, testPath )

        testSched = { "-G": "12", "-L": "testThing" }

        testHeader.scheduler_macros = testSched

        self.assertEqual( testHeader.scheduler_macros, testSched )

        # Testing reset functionality.
        testHeader.reset()

        self.assertEqual( scriptcomposer.scriptHeader().shell_path,
                          testHeader.shell_path )
        self.assertEqual( scriptcomposer.scriptHeader().scheduler_macros,
                          testHeader.scheduler_macros )
        self.assertEqual( testHeader.shell_path, None )
        self.assertEqual( testHeader.scheduler_macros, None )

        # Testing initialization assignment.
        testPath = "/usr/env/python"
        testSched = { "-g": "9", "-m": "testThing" }

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
            testHeader = scriptcomposer.testHeader( shell_path=7,
                                                    scheduler_macros=testSched
                                                  )

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.testHeader( shell_path=testPath,
                                                    scheduler_macros=[
                                                    '-G 12', '-L testThing' ] )

        with self.assertRaises( TypeError ):
            testHeader = scriptcomposer.testHeader( shell_path=12,
                                                    scheduler_macros=13 )
