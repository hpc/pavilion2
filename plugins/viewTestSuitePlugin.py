#!python
""" plug-in to view the test suite configurations 
"""

import os,sys
import logging
from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig


class ViewTestSuite(IPlugin):
    """ This implements the plug-in, or command, to view the default, user, and
        effective (combined) test suite configuration files.
    """

    def __init__(self):
        my_name = self.__class__.__name__

        # If you want the log output from this class to reside in the
        # main (pth) log file you tack it's name onto the pth name space
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('created instance of plugin: %s'% my_name)

    # Every plugin class MUST have a method by the name "add_parser_info
    # and must return the name of the this sub-command

    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("view_test_suite", help="view test suite config files")
        parser_rts.add_argument('testSuite', help='test-suite-config-file')
        parser_rts.add_argument('-d', "--dict", help='show in dictionary format (yaml default)', action="store_true")
        parser_rts.set_defaults(sub_cmds='view_test_suite')
        return ('view_test_suite')

    # Every plug-in class MUST have a method by the name "cmd"
    # so that it can called when its sub-command is selected
        
    def cmd(self, args):

        if args['verbose']:
            print "Command args -> %s" % args
            #print "input test suite file -> %s\n" % args['testSuite']
        
        if (os.path.isfile(args['testSuite'])):
            with open(args['testSuite']) as file:
                # Build the test configuration
                tc = YamlTestConfig(args['testSuite'])
                
            if args['dict']:
                
                print "\nUser test suite configuration (dict style):"
                print tc.get_user_test_config()
                
                print "\nDefault test suite configuration (dict style):"
                print tc.get_default_test_config()
  
                print "\nEffective test configuration (dict style, combined User and Default):"
                print tc.get_effective_config_file()

            else:

                print "\nUser test suite configuration (yaml style):"
                tc.show_user_test_config()
    
                print "\nDefault test suite configuration (yaml style):"
                tc.show_default_config()
    
                print "\nEffective test suite configuration (yaml style, combined User and Default):"
                tc.show_effective_config_file()

        else:
            print "  Error: could not find test suite %s" % args['testSuite']
            sys.exit()
        

if __name__=="__main__":
    print ViewTestSuite.__doc__
