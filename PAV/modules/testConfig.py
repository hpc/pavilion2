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


import sys
import os
from yaml import load, YAMLError
import json
import logging
from testEntry import TestEntry


def merge(obj_1, obj_2):
    """
    Recursive function to merge nested dictionaries
    with obj_2 winning conflicts
    """
    if isinstance(obj_1, dict) and isinstance(obj_2, dict):
        result = {}
        for key, value in obj_1.iteritems():
            if key not in obj_2:
                result[key] = value
                #print "adding key: %s, val: %s, to eff entry" % (key, value)
            else:
                result[key] = merge(value, obj_2[key])
        for key, value in obj_2.iteritems():
            if key not in obj_1:
                result[key] = value
                #print "adding key: %s, val: %s, to eff entry" % (key, value)
        return result
    if isinstance(obj_1, list) and isinstance(obj_2, list):
        #print "combining objects"
        #print obj_1
        #print obj_2
        #return obj_1 + obj_2
        return obj_2
    return obj_2


class YamlTestConfig():
    """
    class to manipulate test suite config files being used
    """

    def __init__(self, ucf="../test_suites/user_test_config.yaml"):

        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pav.' + my_name)

        # Unless defined otherwise in the user's test suite config file the 
        # default config file is found in the same directory.
        test_suite_dir = os.path.dirname(os.path.realpath(ucf)) + "/"
        self.dcf = test_suite_dir + "default_test_config.yaml"

        print "  User test suite file -> " + ucf
        self.user_config_doc = self.load_config_file(ucf)

        if "DefaultTestSuite" in self.user_config_doc:
            df = self.user_config_doc['DefaultTestSuite']
            if "/" not in df:
                self.dcf = test_suite_dir + df
            else:
                self.dcf = df
        print "  Default test suite config file -> " + self.dcf
        self.logger.info('Using default test config file: %s ' % self.dcf)

        self.default_config_doc = self.load_config_file(self.dcf)
        self.ecf = self.create_effective_config_file()

    def load_config_file(self, config_name):
        """
        Load the YAML configuration file(s) with the given name. Returns
        the loaded contents as a dict.
        """
        try:
            # Support test_suites that include other test_suites.
            # Could be recursive, but two levels for now.
            config_file_base_dir = os.path.dirname(config_name)
            fn = config_name
            cfg = load(open(fn))
            for inc in cfg.get("IncludeTestSuite", []):
                fn = config_file_base_dir + "/" + inc
                print "  Included test suite ->  " + fn
                inc_cfg = (load(open(fn)))
                for inc2 in inc_cfg.get("IncludeTestSuite", []):
                    fn = config_file_base_dir + "/" + inc2
                    print "    Included test suite ->  " + fn
                    inc_cfg.update(load(open(fn)))
                cfg.update(inc_cfg)
            return cfg

        except AttributeError:
            error_message = " Badly formatted Include line in {0}\n".format(fn)
            self.logger.error(error_message)
            error_message += "  -> " + cfg
            sys.exit(error_message)

        except EnvironmentError as err:
            error_message = "Error processing item: {0}\n".format(fn)
            self.logger.error(error_message)
            error_message += "I/O Error({0}): {1}.".format(err.errno, 
                                                           err.strerror)
            sys.exit(error_message)

        except YAMLError as err:
            error_message = "YAML Error: {0}".format(err)
            self.logger.error(error_message)
            sys.exit(error_message)

    def get_result_locations(self):
        rl = []
        for k, v in self.ecf.iteritems():
            if type(v) is not dict:
                continue
            te = TestEntry(k, v, None)
            res_loc = te.get_results_location()
            # no need to repeat the location
            if res_loc not in rl:
                rl.append(res_loc)
        return rl

    def show_user_test_config(self):
        """
        Display the users test config file
        """
        print json.dumps(self.user_config_doc, sort_keys=True, indent=4)

    def show_default_config(self):
        """
        Display the system default test config file
        """
        print json.dumps(self.default_config_doc, sort_keys=True, indent=4)

    def create_effective_config_file(self):
        """
        Return the complete test suite file to be used for this test
        after it is folded in with the default configuration
        """

        # get a copy of the default configuration for a test 
        dk, default_config = self.default_config_doc.items()[0]

        # then, for each new test entry (stanza) in the user_config_doc
        # merge with the default entry (overriding the defaults)
        new_dict = {}
        for test_id, v in self.user_config_doc.items():
            # only use "good" entries
            if type(v) is dict:
                if not TestEntry.check_valid(v):
                    print ", skipping (%s) due to invalid entry" % test_id
                    continue
            tmp_config = default_config.copy()

            # merge the user dictionary with the default configuration. Tried
            # other dict methods ( "+", chain, update) and these did not work with nested dict.
            new_dict[test_id] = merge(tmp_config, self.user_config_doc[test_id])

        return new_dict

    def get_effective_config_file(self):
        return self.ecf

    def show_effective_config_file(self):
        """
        Display the effective config file
        """
        #ecf = self.get_effective_config_file()
        print json.dumps(self.ecf, sort_keys=True, indent=4)


    # this gets called if it's run as a script/program
if __name__ == '__main__':

    # instantiate a class to handle the config files
    x = YamlTestConfig()

    print "-------"
    print "\nMy test suite configuration:"
    x.show_user_test_config()

    print "\nDefault test suite configuration (yaml style):"
    x.show_default_config()

    print "\nEffective test suite configuration (yaml style):"
    x.show_effective_config_file()

    print "\nEffective test configuration (dict style):"
    new_config = x.get_effective_config_file()
    print new_config

    print "\nDefault test suite configuration (dict style):"
    dtc = x.default_config_doc
    print dtc

    #f = lambda x: x.bad_type(x)

    sys.exit()
