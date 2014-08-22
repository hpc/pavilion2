#!python

""" plug-in that implements the run_test_suite command 
"""

import os,sys
from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
import subprocess
import json
import logging
from testEntry import TestEntry


    
class RunTestSuite(IPlugin):
    """ This implements the plug-in, or command, to run a suite of tests as
        defined in the users test suite configuration file.
    """

    def __init__(self):
        #print sys.path
        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('created instance of plugin: %s' % my_name)

    def job_dispatcher(self, my_te):
        n = str(my_te.get_nnodes())
        p = str(my_te.get_ppn())
        var = (n,p)
        js_var = json.dumps(var)
        params = my_te.get_values()
        js_params = json.dumps(params)
        self.logger.info('dispatch: %s, variation: (%s x %s)' % (my_te.name, n, p))
        args = ["python", "../modules/runjob.py", my_te.name, js_params, js_var]
        subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)


    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the the sub-command

    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("run_test_suite", help="run each test in the test suite")
        parser_rts.add_argument('testSuite', help='test-suite-config-file')
        parser_rts.add_argument('-d', "--debug", help="don't run, show what would be done", action="store_true")
        parser_rts.set_defaults(sub_cmds='run_test_suite')
        return ('run_test_suite')

    # Every plug-in(command) class MUST have a method by the name "cmd"
    # so that it can called when its sub-command is selected
        
    def cmd(self, args):

        if args['verbose']:
            print "Command args -> %s" % args
            print "TestSuite search path -> " + os.path.dirname(os.path.realpath(args['testSuite']))
        
        if (os.path.isfile(args['testSuite'])):
            with open(args['testSuite']) as file:

                # Use the default (or master) test suite configuration from the same directory
                #dts = os.path.dirname(os.path.realpath(args['testSuite'])) + "/default_test_config.yaml"
                # Build the test configuration
                #tc = YamlTestConfig(args['testSuite'], dts)
                tc = YamlTestConfig(args['testSuite'])
                if args['verbose']:
                    print "User test suite:"
                    utc = tc.get_user_test_config()
                    print "  %s" % utc

                # get the "merged" test stanza for each test in the test suite
                my_test_suite = tc.get_effective_config_file()

                # Process and launch a new test for each test entry (stanza) in the test suite
                # and its variations here.
                for name, params in my_test_suite.iteritems():


                    if "DefaultTestSuite" in name:
                        continue

                    te = TestEntry(name,params,args)
                    test_type = te.get_type()
                    #print "my test type -> " + test_type

                    test_variants = [(None)]
                    # get list of "new" test entries
                    if ("moab" in test_type):
                        test_variants = te.get_test_variations()
                        for test_entry in test_variants:
                            for _ in range(te.get_run_times()):
                                self.job_dispatcher(test_entry)
                    else:
                        for _ in range(te.get_run_times()):
                            self.job_dispatcher(te)


                 #   count = 1
                    # If there is one test variation then allow multiple runs,
                    # otherwise run only ONCE for each variation
                 #   if (test_variants.__len__()  == 1):
                 #      count = te.get_count()

                    # new process for each test variation
                #    for test_entry in test_variants:
                 #   for test_entry in test_variants.__iter__():
                 #       print var, type(var)
                 #       for _ in range(count):
                #          if isinstance(var, tuple):
                 #               self.logger.info('dispatch: %s, variation: (%s x %s)' % (name, var[0], var[1]))
                 #           else:
                #             self.logger.info('dispatch: %s, variations: %s' % (name, var))
                 #           job_dispatcher(name, params, var)
                 #           job_dispatcher2(test_entry)
        else:
            print "  Error: could not find test suite %s" % args['testSuite']
            sys.exit()
        

if __name__=="__main__":
    print RunTestSuite.__doc__
