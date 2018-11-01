#!/usr/bin/env python

#  ###################################################################
#
#  Disclaimer and Notice of Copyright 
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC. 
#  This software was produced under U.S. Government contract 
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), 
#  which is operated by Los Alamos National Security, LLC for 
#  the U.S. Department of Energy. The U.S. Government has rights 
#  to use, reproduce, and distribute this software.  NEITHER 
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES 
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY 
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to 
#  produce derivative works, such modified software should be 
#  clearly marked, so as not to confuse it with the version 
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary 
#  forms, with or without modification, are permitted provided 
#  that the following conditions are met:
#  -  Redistributions of source code must retain the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer. 
#  -  Redistributions in binary form must reproduce the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution. 
#  -  Neither the name of Los Alamos National Security, LLC, 
#     Los Alamos National Laboratory, LANL, the U.S. Government, 
#     nor the names of its contributors may be used to endorse 
#     or promote products derived from this software without 
#     specific prior written permission.
#   
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC 
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS 
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, 
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY 
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
#  OF SUCH DAMAGE.
#
#  ###################################################################


""" plug-in that implements the run_test_suite command 
"""

import os
import sys
import subprocess
import json
import logging
import time
import itertools

from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
from testEntry import TestEntry, MoabTestEntry, RawTestEntry, SlurmTestEntry

## Assumes ../modules is in sys.path. Better if packaged, then looks like:
#from .. import runjob
import runjob
from basejobcontroller import JobException

def decompose_str( in_str ):
    """
    Function to take a string of the form key1.key2.key3.key4=res1 and return
    a nested dictionary.
    """
    if '.' in in_str:
        str_list = in_str.split('.')
        return { str_list[0] : decompose_str('.'.join(str_list[1:]) ) }
    elif '=' in in_str:
        key, val = in_str.split('=')
        return { key : val }
    else:
        error_message = "Custom parameter was malformed.\n Appropriate format is:\n" + \
                        "-c key1.key2.key3.key4=value."
        sys.exit(error_message)

def modify_dict( master_dict, replacement_key, replacement_val ):
    """
    Takes a custom parameter modifying dictionary created by decompose_str()
    and uses it to find the appropriate entry in the master configuration
    directory and modifies the value to the new value.
    """
    if not isinstance( master_dict, dict ) or \
       ( isinstance( master_dict, dict ) and \
         len( master_dict ) == 1 and \
         master_dict.vals() == [ null ] ):
        return None
    elif not isinstance( replacement_val, dict ) and not isinstance( replacement_val, list ):
        master_dict[replacement_key] = replacement_val
        return master_dict
    elif replacement_key not in master_dict.keys():
        error_message = "Custom parameter was not found in the configuration."
        sys.exit(error_message)
    else:
        master_dict[replacement_key] = modify_dict( master_dict[replacement_key],
                                                    replacement_val.keys()[0],
                                                    replacement_val.values()[0] )
        return master_dict


def expansion (initial_arguements, initial_restrictions):
    list_of_lists=[]
    my_list=[]
    temp_list=[]
    temp_string=""
    return_list_of_strings=[]

    # check to see if inital arguments in an array. if not we can just return it
    if (not isinstance(initial_arguements, list)):
        return initial_arguements

    ## Definitions of variables ## {{{
    #   lists_of_lists will store the lists arguements passed in
    #   my_list will store all the combinations of the lists passed in
    #   temp_list will store the complete array of arguements after 
    #       expansion, but will not keep previous data
    #   temp_string will store the complete string of arguements
    #       but will not keep previous data
    #   return_list_of_strings hold all complete and valid arguement 
    #       strings to be returned.
    ## }}}
    ## Code ##{{{
    #   Check if the user has passed in a list of other than one 
    #       dimension
    #       Then create a string of all arguements
    #       Check if any of the restrictions are met, whether they are
    #           one dimensional or two,
    #           returns an empty string if they are
    #           returns the string of all arguements if they are not
    #   If the arguement list is not single dimensional list
    #       Then create every combination of the intial_arguements
    #       For each combination,
    #           Check if any of the restrictions are met, whether they 
    #           are one dimensional or two,
    #       returns the list of all strings of all arguement 
    #           combinations that are not restricted
    ## }}}
    if (all((type(arguement) != list) for arguement in initial_arguements)):
        for iterator in initial_arguements:
            temp_string=str(iterator)
            if ( (any (((type(restrictions) != list) 
                and (restrictions in temp_string)) 
                for restrictions in initial_restrictions) ) 
                or ( (any((type(restrictions) == list) 
                for restrictions in initial_restrictions)) 
                and (any ((all ((restriction in temp_string) 
                for restriction in restrictions)) 
                for restrictions in initial_restrictions)) )): 
                pass
            else:
                return_list_of_strings.append(temp_string)
    else:
        for arguement in initial_arguements:
            list_of_lists.append(arguement)
        my_list=list(itertools.product(*list_of_lists))
        for i in my_list:
            for j in i:
                temp_list.append(j)
            for iterator in temp_list:
                temp_string+=iterator+" "
            if ( (any (((type(restrictions) != list) 
                and (restrictions in temp_string)) 
                for restrictions in initial_restrictions) ) 
                or ( (any((type(restrictions) == list) 
                for restrictions in initial_restrictions)) 
                and (any ((all ((restriction in temp_string) 
                for restriction in restrictions)) 
                for restrictions in initial_restrictions)) )): 
                pass
            else:
                return_list_of_strings.append(temp_string)
            temp_list=[ ]
            temp_string=""
    return return_list_of_strings



class RunTestSuite(IPlugin):
    """ This implements the plug-in, or command, to run a suite of tests as
        defined in the user's test suite configuration file.
    """

    def __init__(self):
        #print sys.path
        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pav.' + my_name)
        self.logger.info('created instance of plugin: %s' % my_name)

    def job_dispatcher(self, my_te, in_args):
        #print "dispatch " + my_te.get_id() + " : "
        #print my_te.this_dict[my_te.get_id()]
        params = my_te.get_values()
        js_params = json.dumps(params)
        uid = my_te.get_id()
        lh = uid + "-" + my_te.get_name()
        self.logger.info('dispatch: %s, variation: (%s)' % (lh, my_te.get_id()))
        runjob_cmd = os.environ['PVINSTALL'] + "/PAV/modules/runjob.py"
        master_log_file = os.environ['PV_LOG']
        try: 
            runjob.main([runjob_cmd, uid, js_params, master_log_file])
        except JobException as e:
            print "\nERROR (" + str(e.err_code) + "): " + e.err_str + \
                "\n" + e.msg


    # build the sub-command argument list
    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("run_test_suite", help="run each test in the test suite")
        parser_rts.add_argument('testSuite', help='test-suite-config-file', nargs='?')
        parser_rts.add_argument('-d', "--debug", help="don't run, show what would be done", action="store_true")
        parser_rts.add_argument('-D', nargs=1, metavar='<secs>',
                               help="submit again after delaying this many <secs> - NOT WORKING YET!")
        parser_rts.add_argument('-m', "--ldms",
                                help="start LDMS metrics. Within Moab allocation only", action="store_true")
        #parser_rts.add_argument('-p', nargs=1, metavar='<val>', help="fill host to this percent usage (DRM specific)")
        parser_rts.add_argument('-s', "--serial", help="run jobs serially, default mode is parallel", action="store_true")
        parser_rts.add_argument('-w', nargs=1, metavar='<count>',
                                help="don't submit if <count> of my jobs running or queued (DRM specific)")
        parser_rts.add_argument('-t', "--test", type=str, metavar='<test>', action='append',
                                help="only run <test> in test file. Multiple may be specified.")
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
                secs_to_sleep = int(args['D'][0])
                time.sleep(secs_to_sleep)
                sys.stdout.write('\rRunning in continuous mode with a delay of %s seconds...' % secs_to_sleep)
                sys.stdout.flush()
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
        tc = YamlTestConfig(args['testSuite'], testname=args['testname'], hostname=args['name'], modelist=args['mode'])

        if args['verbose']:
            print "Command args -> %s" % args
            #print "TestSuite search path -> " + os.path.dirname(
            #    os.path.realpath(args['testSuite']))
            # print "User test suite:"
            # print "  %s" % utc

        # get the "merged" test stanza for each test in the test suite
        my_test_suite = tc.get_effective_config_file()

        # Check if custom arguments are specified to change individual parameters
        if args['custom'] != []:
            custom_list = []
            for custom in args['custom']:
                if custom[0] == '*':
                    for key, val in my_test_suite.iteritems():
                        self.logger.info('Expanding custom parameter to %s' % (key + custom[1:]))
                        custom_list.append( key + custom[1:] )
            for custom in custom_list:
                if '.' in custom:
                    custom_dict = decompose_str( custom )
                    modify_dict( my_test_suite, custom_dict.keys()[0], custom_dict.values()[0] )
                else:
                    my_test_suite[ custom.split('=')[0] ] = custom.split('=')[1]

        # if we are running in debug mode we are then done because we do not need
        # to submit anything
        if args['debug']:
            return

        # Process and launch each test entry (stanza) from the test suite.
        submit_again = True
        while submit_again:
            for entry_id, test_suite_entry in my_test_suite.iteritems():

                # Don't process the DTS definition
                if "DefaultTestSuite" in entry_id:
                    continue
                # Don't process include directive
                if "IncludeTestSuite" in entry_id:
                    continue
                # Don't process it it is not in the test list (if a test list is specified)
                if args['test']:
                    if entry_id not in args['test']:
                        if args['verbose']:
                            print "Skipping %s" % entry_id
                        continue

                # instantiate a new object for each test Entry type  ( Raw, Moab, etc. )
                # i.e. , te = MoabTestEntry(...)
                try:
                    st = test_suite_entry['run']['scheduler']
                    scheduler_type = st.capitalize()
                except AttributeError:
                    scheduler_type = "Raw"

                # There needs to be this type of scheduler object implemented to support this
                # See the testEntry.py file for examples
                object_name = scheduler_type + "TestEntry"

                test_args_restrictions = []
                if 'test_args_restrictions' in test_suite_entry['run'] and test_suite_entry['run']['test_args_restrictions']:
                    test_args_restrictions = test_suite_entry['run']['test_args_restrictions']
                test_suite_entry['run']['test_args']=expansion(test_suite_entry['run']['test_args'], test_args_restrictions)

                try:
                    te = globals()[object_name](entry_id, test_suite_entry, args)
                except KeyError:
                    raise ValueError(scheduler_type + " scheduler type not supported (check the test entry), exiting!")

                # If user specifies a max level of jobs to queue and run (watermark) then
                # don't launch a new set if this level is reached.
                if (args['w'] and te.room_to_run(args)) or not args['w']:
                    # print "plenty of room to run"
                    # launch a new process for each test variation and/or count
                    for test_entry in te.get_test_variations():
                        # initialize a unique LDMS for each job
                        os.environ['LDMS_START_CMD'] = ''
                        if args['ldms'] or ('ldms' in test_suite_entry and test_suite_entry['ldms']['state']):
                            #print test_suite_entry['ldms']['state']
                            te.prep_ldms()

                        for _ in range(te.get_run_count()):
                            #print "dispatch with:"
                            #print test_entry.get_id()
                            self.job_dispatcher(test_entry, args)

            submit_again = RunTestSuite.submit_delay(args)

if __name__ == "__main__":
    print RunTestSuite.__doc__
