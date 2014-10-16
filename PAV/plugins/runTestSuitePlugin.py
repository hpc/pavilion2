#!/usr/bin/env python

""" plug-in that implements the run_test_suite command 
"""

import os
import sys
import subprocess
import json
import logging
import time

from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
from testEntry import TestEntry, MoabTestEntry, RawTestEntry
from ldms import LDMS


class RunTestSuite(IPlugin):
    """ This implements the plug-in, or command, to run a suite of tests as
        defined in the user's test suite configuration file.
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
        parser_rts.add_argument('-D', nargs=1, metavar='<secs>',
                                help="submit again after delaying this many <secs>")
        parser_rts.add_argument('-m', "--ldms",
                                help="start LDMS metrics. Within Moab allocation only", action="store_true")
        #parser_rts.add_argument('-p', nargs=1, metavar='<val>', help="fill host to this percent usage (DRM specific)")
        parser_rts.add_argument('-w', nargs=1, metavar='<count>',
                                help="don't submit if <count> of my jobs running or queued (DRM specific)")
        parser_rts.set_defaults(sub_cmds='run_test_suite')
        return 'run_test_suite'

    @staticmethod
    def submit_delay(args):
        """
        Delay for continuous submissions, or develop another method to trigger
        jobs.
        """
        try:
            if args['D']:
                time.sleep(int(args['D'][0]))
                return True
        except:
            raise ValueError("Error: invalid delay time argument!")

        return False

    def cmd(self, args):
        """
        Every class used as a plugin (sub-command) MUST have a method
        by the name of cmd. This is executed when the given sub-command
        is executed.
        """
        # Build the test configuration
        tc = YamlTestConfig(args['testSuite'])
        utc = tc.user_config_doc

        if args['verbose']:
            print "Command args -> %s" % args
            print "TestSuite search path -> " + os.path.dirname(
                os.path.realpath(args['testSuite']))
            print "User test suite:"
            print "  %s" % utc

        # get the "merged" test stanza for each test in the test suite
        my_test_suite = tc.get_effective_config_file()

        # Process and launch each test entry (stanza) from the test suite.
        submit_again = True
        while submit_again:
            for entry_id, params in my_test_suite.iteritems():

                # Don't process the DTS definition
                if "DefaultTestSuite" in entry_id:
                    continue

                # instantiate a new object for each test Entry type  ( raw, Moab, etc. )
                scheduler_type = params['run']['scheduler'].capitalize()
                object_name = scheduler_type + "TestEntry"
                # i.e. , te = MoabTestEntry(...)
                te = globals()[object_name](entry_id, params, args)

                #test_type = te.get_type()
                #print "my test type -> " + test_type

                #test_variants = [None]
                # get list of "new" test entries
                # launch a new process for each test variation or count
                #test_variants = te.get_test_variations()
                #if "moab" in test_type:
                    #test_variants = te.get_test_variations()
                for test_entry in te.get_test_variations():
                    # support w argument for now, add p later
                    if (args['w'] and te.room_to_run(args)) or not args['w']:
                        # initialize a unique LDMS for each job, if requested
                        os.environ['LDMS_START_CMD'] = ''
                        if args['ldms']:
                            #LDMS(te)
                            te.prep_ldms()

                        for _ in range(te.get_run_count()):
                            self.job_dispatcher(test_entry)
                #else:
                #    for _ in range(te.get_run_count()):
                #        self.job_dispatcher(te)

            submit_again = RunTestSuite.submit_delay(args)

if __name__ == "__main__":
    print RunTestSuite.__doc__
