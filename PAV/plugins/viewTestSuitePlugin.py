#!python

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


""" plug-in to view the test suite configurations 
"""

import os,sys
import json
import logging
from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig

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


class ViewTestSuite(IPlugin):
    """ This implements the plug-in, or command, to view the default, user, and
        effective (combined) test suite configuration files.
    """

    def __init__(self):
        my_name = self.__class__.__name__

        # If you want the log output from this class to reside in the
        # main (pav) log file you tack it's name onto the pav name space
        self.logger = logging.getLogger('pav.' + my_name)
        self.logger.info('created instance of plugin: %s'% my_name)

    # Every plugin class MUST have a method by the name "add_parser_info
    # and must return the name of the this sub-command

    def add_parser_info(self, subparser): 
        parser_rts = subparser.add_parser("view_test_suite",
                                          help="view test suite config files (user, default, and combined)")
        parser_rts.add_argument('testSuite', help='test-suite-config-file', nargs='?')
        parser_rts.add_argument('-d', "--dict", help='show in dictionary format (yaml default)', action="store_true")
        parser_rts.set_defaults(sub_cmds='view_test_suite')
        return ('view_test_suite')

    # Every plug-in (command) MUST have a method by the name "cmd".
    # It will be what is called when that command is selected.
    def cmd(self, args):

        if args['verbose']:
            print "Command args -> %s" % args
            #print "input test suite file -> %s\n" % args['testSuite']

        tc = YamlTestConfig(args['testSuite'], testname=args['testname'], hostname=args['name'], modelist=args['mode'])
                
        if args['dict']:
            
            print "\nUser test suite configuration (dict style):"
            print tc.user_config_doc
            
            print "\nDefault test suite configuration (dict style):"
            print tc.default_config_doc

            print "\nEffective test configuration (dict style, combined User and Default):"

            # Check if custom arguments are specified to change individual parameters
            my_test_suite = tc.get_effective_config_file()
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
            print my_test_suite

        else:

            print "\nUser test suite configuration (yaml style):"
            tc.show_user_test_config()

            print "\nDefault test suite configuration (yaml style):"
            tc.show_default_config()

            print "\nEffective test suite configuration (yaml style, combined User and Default):"

            # Check if custom arguments are specified to change individual parameters
            my_test_suite = tc.get_effective_config_file()
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
            print json.dumps( my_test_suite, sort_keys=True, indent=4)


if __name__=="__main__":
    print ViewTestSuite.__doc__
