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
import logging
import itertools
from testEntry import TestEntry



def job_dispatcher(name, params, var):

    # Run the job as its own detached subprocess so that we do not wait on long running jobs
    # Jobs have the potential to "run" for days...

    js_params = json.dumps(params)
    js_var = json.dumps(var)
    args = ["python", "../modules/runjob.py", name, js_params, js_var]
    subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    
class RunTestSuite(IPlugin):
    """ This implements the feature to run/launch a suite of tests as
        defined in the users test suite configuration file.
    """

    def __init__(self):
        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('created instance of plugin: %s' % my_name)


    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the this sub-command

    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("run_test_suite", help="run each test in the test suite")
        parser_rts.add_argument('testSuite', help='test-suite-config-file')
        parser_rts.add_argument('-d', "--debug", help="don't run, show what would be done", action="store_true")
        parser_rts.set_defaults(sub_cmds='run_test_suite')
        return ('run_test_suite')

    # Every plug-in(command) class MUST have a method by the name "cmd"
    # so that it can called when its sub-command is selected
        
    def cmd(self, args):

        print "invoke: run_test_suite "
        if args['verbose']:
            print "args -> %s" % args
        
        if (os.path.isfile(args['testSuite'])):
            with open(args['testSuite']) as file:

                # Build the test configuration
                tc = YamlTestConfig(args['testSuite'])

                # get the "merged" test stanza for each test in the test suite
                my_test_suite = tc.get_effective_config_file()

                #for stanza in my_test_suite.iteritems():
                    #print "\n"
                    #print stanza
                    #print "\n"

                # Process each test entry (stanza) in the test suite
                # Name had better be unique
                for name, params in my_test_suite.iteritems():

                    test_type = TestEntry.get_test_type(params)
                    #print test_type
                    te = TestEntry(name,params)

                    test_variants = [(None)]
                    # get list of tuples for each test variation
                    if ("moab" in test_type):
                        test_variants = te.get_moab_test_variations()

                    count = 1
                    # If there is one test variation then allow multiple runs,
                    # otherwise run only ONCE for each variation
                    if (test_variants.__len__()  == 1):
                       count = te.get_test_count()

                    # new process for each test variation
                    for var in test_variants.__iter__():
                        for _ in range(count):
                            self.logger.info('dispatch: %s, variation: %s' % (name, var))
                            job_dispatcher(name, params, var)
        else:
            print "  Error: could not find test suite %s" % args['testSuite']
            sys.exit()
        

if __name__=="__main__":
    print RunTestSuite.__doc__
