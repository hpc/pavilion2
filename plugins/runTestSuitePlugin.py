#!python

""" plug-in that implements the run_test_suite command 
"""

import os,sys
import types
from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
import time
import datetime
import multiprocessing
import daemon
import subprocess
import json


def job_dispatcher(name, params):

    # Run the job as it's own detached subprocess so that the program can return
    # These jobs have the potential to "run" for days...

    js_params = json.dumps(params)
    args = ["python", "../modules/runjob.py", name, js_params]
    print "runTestSuitePlugin: dispatch job -> %s:" % name
    subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)


    
class RunTestSuite(IPlugin):
    """ This implements the feature to run/launch a suite of tests as
        defined in the users test suite configuration file.
    """

    def print_name(self):
        print "runTestSuite handler loaded!"

    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the this sub-command

    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("run_test_suite", help="run each test in the test suite")
        parser_rts.add_argument('testSuite', help='test-suite-config-file')
        parser_rts.add_argument('-d', "--debug", help="don't run, show what would be done", action="store_true")
        parser_rts.set_defaults(sub_cmds='run_test_suite')
        return ('run_test_suite')

    # Every plug-in class MUST have a method by the name "cmd"
    # so that it can called when its sub-command is selected
        
    def cmd(self, args):
        print "\n"
        if args['verbose']:
            print "\nrunning run_test_suite"
            print "args -> %s" % args
            print "using test suite -> %s\n" % args['testSuite']
        
        if (os.path.isfile(args['testSuite'])):
            with open(args['testSuite']) as file:
                # Build the test configuration
                tc = YamlTestConfig(args['testSuite'])
                # get the "folded" test stanza for each test in the test suite
                my_test_suite = tc.get_effective_config_file()
                # just loop over each test and "run" it
                #for te in my_test_suite.iteritems():
                    #print type(te[0]), type(te[1])
                for name, test_params in my_test_suite.iteritems():
                    if args['verbose']:
                        print " -> run %s: from %s using params %s:" % (name, test_params['source_location'], test_params['run'])
                    job_dispatcher(name, test_params)
        else:
            print "  Error: could not find test suite %s" % args['testSuite']
            sys.exit()
        

if __name__=="__main__":
    print RunTestSuite.__doc__
