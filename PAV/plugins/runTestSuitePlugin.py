#!python

""" plug-in that implements the run_test_suite command 
"""

import os
import sys
import subprocess
import json
import logging

from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
from testEntry import TestEntry
from ldms import LDMS


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
        uid = my_te.get_id()
        lh = uid + "-" + my_te.get_name()
        self.logger.info('dispatch: %s, variation: (%s x %s)' % (lh, n, p))
        runjob_cmd = os.environ['PVINSTALL'] + "/PAV/modules/runjob.py"
        args = ["python", runjob_cmd, uid, js_params, js_var]
        subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)

    # build the sub-command argument list
    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("run_test_suite", help="run each test in the test suite")
        parser_rts.add_argument('testSuite', help='test-suite-config-file')
        parser_rts.add_argument('-d', "--debug", help="don't run, show what would be done", action="store_true")
        parser_rts.add_argument('-m', "--ldms",
                                help="start LDMS metrics. Within Moab allocation only", action="store_true")
        parser_rts.set_defaults(sub_cmds='run_test_suite')
        return 'run_test_suite'

    # Every plug-in(command) class MUST have a method by the name "cmd"
    # so that it can called when it's selected
    def cmd(self, args):

        if args['verbose']:
            print "Command args -> %s" % args
            print "TestSuite search path -> " + os.path.dirname(os.path.realpath(args['testSuite']))
        
        try:
            with open(args['testSuite']) as af:

                # Use the default (or master) test suite configuration from the same directory
                #dts = os.path.dirname(os.path.realpath(args['testSuite'])) + "/default_test_config.yaml"
                # Build the test configuration
                tc = YamlTestConfig(args['testSuite'])
                utc = tc.get_user_test_config()
                if args['verbose']:
                    print "User test suite:"
                    print "  %s" % utc

                # get the "merged" test stanza for each test in the test suite
                my_test_suite = tc.get_effective_config_file()

                # Process and launch a new test for each test entry (stanza) in the test suite
                # and its variations here.
                for entry_id, params in my_test_suite.iteritems():

                    # This just defines where to find a different DTS, so
                    # skip this entry.
                    if "DefaultTestSuite" in entry_id:
                        continue

                    te = TestEntry(entry_id, params, args)

                    test_type = te.get_type()
                    #print "my test type -> " + test_type

                    test_variants = [None]
                    # get list of "new" test entries
                    # launch a new process for each test variation or count
                    if "moab" in test_type:
                        test_variants = te.get_test_variations()
                        for test_entry in test_variants:

                            # initialize a unique LDMS for each job, if requested
                            os.environ['LDMS_START_CMD'] = ''
                            if args['ldms']:
                                LDMS(te)

                            for _ in range(te.get_run_times()):
                                self.job_dispatcher(test_entry)
                    else:
                        for _ in range(te.get_run_times()):
                            self.job_dispatcher(te)

        except EnvironmentError as err:
            print "  Error: could not access test suite %s" % args['testSuite']
            sys.exit()
        

if __name__ == "__main__":
    print RunTestSuite.__doc__
