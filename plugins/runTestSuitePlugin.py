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


def job_dispatcher(name, params):

    # Run the job as it's own detached subprocess so that the program can return
    # These jobs have the potential to "run" for days...

    js_params = json.dumps(params)
    args = ["python", "../modules/runjob.py", name, js_params]
    #print "runTestSuitePlugin: dispatch job -> %s:" % name
    subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

def get_test_variations(params):

    # figure out all the (node by pe) variations for this test
    # and return tuple of choices
    tv = [ (1,16), (4,8) ]
    return tv


    
class RunTestSuite(IPlugin):
    """ This implements the feature to run/launch a suite of tests as
        defined in the users test suite configuration file.
    """

    def __init__(self):
        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('created instance of plugin: %s'% my_name)


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

        print "run_test_suite:"
        if args['verbose']:
            print "args -> %s" % args
        
        if (os.path.isfile(args['testSuite'])):
            with open(args['testSuite']) as file:
                # Build the test configuration
                tc = YamlTestConfig(args['testSuite'])
                # get the "folded" test stanza for each test in the test suite
                my_test_suite = tc.get_effective_config_file()

                # just loop over each test variation and "run" it
                for name, params in my_test_suite.iteritems():
                    # get list of tuple variations ((nodes X pes ), ...]
                    test_variants = get_test_variations(params)
                    #test_variants = [ (1,16) ]
                    #test_variants = [ (1,16), (4,8) ]
                    count = 1
                    # allow multiple runs, only if there is one test variation
                    if (test_variants.__len__()  == 1):
                       count = int(params['run']['count'])

                    for nnodes, npes in test_variants:
                        for _ in range(count):
                            params['eff_nnodes'] = nnodes
                            params['eff_npes'] = npes
                            self.logger.info('dispatch %s (%s x %s)' % (name, nnodes, npes))
                            if args['verbose']:
                                print " -> run %s: using %s, nnodes - %s, npes - %s" % \
                                    (name, params['source_location'] + "/" + params['run']['cmd'], nnodes, npes)
                            job_dispatcher(name, params)
        else:
            print "  Error: could not find test suite %s" % args['testSuite']
            sys.exit()
        

if __name__=="__main__":
    print RunTestSuite.__doc__
