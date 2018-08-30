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
import re
import json
import logging
import subprocess
from yaml import load, YAMLError

import traceback

#from PAV.modules.testEntry import TestEntry
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
                if key == "UniqueId":
                    for key1, value1 in obj_2.iteritems():
                        result[key1] = merge( obj_1["UniqueId"], obj_2[key1] )
                result[key] = value
                #print "adding key: %s, val: %s, to eff entry" % (key, value)
            else:
                if isinstance( value, dict ) and isinstance( obj_2[key], dict ):
                    result[key] = merge( value, obj_2[key] )
                elif isinstance(value, int) and isinstance(obj_2[key], int) and value < obj_2[key]:
                    error_message = "Value provided {} is greater than the allowed value {}.".format( obj_2[key], value )
                    sys.exit( error_message )
                else:
                    result[key] = merge(value, obj_2[key])
        for key, value in obj_2.iteritems():
            if key not in result.keys():
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

def modify_dict( master_dict, replacement_key, replacement_val ):
    """
    Takes a custom parameter modifying dictionary created by decompose_str()
    and uses it to find the appropriate entry in the master configuration
    directory and modifies the value to the new value.
    """
    if not isinstance( replacement_val, dict ) and not isinstance( replacement_val, list ):
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

def load_metaconfig(cfg_script):
    # Load a dict from a script that produces key=value pairs
    if cfg_script is not None:
        query = os.environ['PVINSTALL'] + "/PAV/" + cfg_script
        if os.path.exists(query):
            vars_str = subprocess.check_output(query, shell=True).strip()
            return {k:v.strip('"')
                    for k,v in re.findall(r'(\S+)=(".*?"|\S+)', vars_str)}
    return {}

def decode_metavalue(value, cfg_script="scripts/site/metaconfig.sh"):
    # Substitute instances of @{KEY} with the associated value in a string
    var_cfg = load_metaconfig(cfg_script)
    for varkey, varval in var_cfg.iteritems():
        encodedvar = "@{" + varkey + "}"
        if encodedvar in value:
            value = value.replace(encodedvar, varval)
    return value

def decode_metaconfig(cfg, cfg_script="scripts/site/metaconfig.sh"):
    # Substitute instances of @{KEY} with the associated value throughout a dict
    var_cfg = load_metaconfig(cfg_script)
    for key, value in cfg.iteritems():
        for varkey, varval in var_cfg.iteritems():
            encodedvar = "@{" + varkey + "}"
            if encodedvar in value:
                cfg[key] = value.replace(encodedvar, varval)
    return cfg



class YamlTestConfig(object):
    """
    class to manipulate test suite config files being used
    """

    # ++ PAV_CFG_ROOT : Root directory for pavilion test configurations
    def __init__(self, ucf=os.path.join(os.environ['PAV_CFG_ROOT'],'blank.yaml'),
                 ccf="scripts/site/metaconfig.sh", testname="",
                 hostname="", modelist=[]):

        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pav.' + my_name)

        # Unless defined otherwise in the user's test suite config file the 
        # default config file is found in the same directory.
        if ucf == None: ucf = os.path.join(os.environ['PAV_CFG_ROOT'],'blank.yaml')
        test_suite_dir = os.path.dirname(os.path.realpath(ucf)) + "/"
        self.dcf = test_suite_dir + "default_test_config.yaml"
        if len(ucf) >= 5 and ucf[-5:] != ".yaml":
            ucf += ".yaml"

        if os.path.isfile(ucf):
            info_msg = "Using %s user config file." % ucf
            self.logger.info( info_msg )
        else:
            error_msg = "User config file %s not found." % ucf
            self.logger.error( error_msg )
            sys.exit( error_msg )

        self.user_config_doc = self.load_config_file(ucf)

        if not isinstance( self.user_config_doc, dict ):
            error_msg = "Loaded test config %s is of the wrong type." % ucf
            error_msg += "\nThe type is %s." % type( self.user_config_doc )
            self.logger.error( error_msg )
            sys.exit( error_msg )

        tmp_cfg = self.extract_nested_tests( self.user_config_doc )

        if tmp_cfg != {'UniqueId': None} and "PAV_CFG_ROOT" in os.environ.keys():
            self.user_config_doc = tmp_cfg

        expanded_config = {}

        for testname, test in self.user_config_doc.iteritems():
            while True:
                test_key, test_val = self.find_expansions(test)
                if test_val == ["empty"] and test_key == "empty":
                    break
                elif test_val == []:
                    continue
                for variant in test_val:
                    expanded_config[testname + '-' + variant] = modify_dict( test, test_key, variant )
            if test_val == ["empty"] and test_key == "empty":
                break

            self.user_config_doc['testname'] = expanded_config

        if "PAV_CFG_ROOT" in os.environ.keys():
            self.cfg_root = os.environ['PAV_CFG_ROOT']
            print "  Configuration root: " + self.cfg_root

            if self.cfg_root[-1] != '/':
                self.cfg_root += '/'

            self.dcf = self.cfg_root + 'default_test_config.yaml'

            print "  Default test suite config file -> " + self.dcf
            self.logger.info('Using default test config file: %s ' % self.dcf)
    
            self.default_config_doc = self.load_config_file(self.dcf)

            # Check for host-specific .yaml file
            if hostname != "":
                self.host=hostname
            else:
                hostname = subprocess.Popen( ['/usr/projects/hpcsoft/utilities/bin/sys_name'],
                                              stdout=subprocess.PIPE, )

                for line in hostname.stdout:
                    self.host = line.strip()

            self.host = self.cfg_root + 'hosts/' + self.host + '.yaml'

            if not os.path.isfile( self.host ):
                error_message = "Host file {} does not exist.\n".format( self.host )
                self.logger.error( error_message )
                sys.exit( error_message )

            print "  Default test suite host config file -> " + self.host
            self.logger.info('Using default test host config file: %s ' % self.host)
            self.host_config_doc = self.load_config_file(self.host)

            self.default_config_doc = merge(self.default_config_doc, self.host_config_doc)

            # Check for mode-specific .yaml file
            if modelist != []:
                self.mode = modelist
            else:
                self.mode = [ "qos-standard" ]

            for mode in self.mode:
                mode = self.cfg_root + 'modes/' + mode + '.yaml'
    
                if not os.path.isfile( mode ):
                    error_message = "Mode file {} does not exist.\n".format( mode )
                    self.logger.error( error_message )
                    sys.exit( error_message )
    
                print "  Default test suite mode config file -> " + mode
                self.logger.info('Using default test mode config file: %s ' % mode)
                self.mode_config_doc = self.load_config_file(mode)
    
                self.default_config_doc = merge( self.default_config_doc, self.mode_config_doc )

            # Check for test-specific .yaml file
            if testname != "":
                self.test = testname
            else:
                self.test = ucf.split('.')[0]

            self.test = self.cfg_root + 'tests/' + self.test.split('.')[0] + '.yaml'

            if testname != "":
                if not os.path.isfile( self.test ):
                    error_message = "Test file {} does not exist. Skipping default test config.\n".format( self.test )
                    self.logger.info( error_message )
                else:
                    print "  Default test suite test config file -> " + self.test
                    self.logger.info('Using default test test config file: %s ' % self.test)
                    self.test_config_doc = self.load_config_file(self.test)
    
                    test_dict = {}
    
                    for test_key, test_val in self.test_config_doc.iteritems():
                        test_dict[test_key] = ( merge( self.default_config_doc['UniqueId'], test_val ) )
    
                    self.default_config_doc = test_dict

            self.ecf = {}

            if self.user_config_doc != {}:
                for subtestname, subtest in self.user_config_doc.iteritems():
                    self.ecf[ subtestname ] = merge( self.default_config_doc[self.default_config_doc.keys()[0]], self.user_config_doc[ subtestname ] )
            else:
                self.ecf = self.default_config_doc

        elif "DefaultTestSuite" in self.user_config_doc:
            df = self.user_config_doc['DefaultTestSuite']
            if "/" not in df:
                self.dcf = test_suite_dir + df
            else:
                self.dcf = df
            print "  Default test suite config file -> " + self.dcf
            self.logger.info('Using default test config file: ' + self.dcf)
            
            self.default_config_doc = self.load_config_file(self.dcf, ccf)
            self.ecf = self.create_effective_config_file()

        elif os.path.isfile( self.dcf ):
            print "  Default test suite config file -> " + self.dcf
            self.logger.info('Using default test config file: ' + self.dcf)
            
            self.default_config_doc = self.load_config_file(self.dcf)
            self.ecf = {}
            for subtestname, subtest in self.user_config_doc.iteritems():
                self.ecf[subtestname] = merge( self.default_config_doc[self.default_config_doc.keys()[0]], self.user_config_doc[subtestname] )

        else:
            error_msg = "Did not find a default configuration file."
            print error_msg
            self.logger.error(error_msg)
            sys.exit(1)

        for test in range(0, len(self.ecf)):
            if 'run' in self.ecf[test].keys()
               and 'test_args' in self.ecf[test]['run'].keys()
               and isinstance(self.ecf[test]['run']['test_args'], list):
                self.ecf[test]['run']['test_args'] = " ".join(self.ecf[test]['run']['test_args'])
                        

    def load_config_file(self, config_name, cfg_script=None):
        """
        Load the YAML configuration file(s) with the given name. Returns
        the loaded contents as a dict.
        """
        try:
            # Support test_suites that include other test_suites.
            # Could be recursive, but two levels for now.
            config_file_base_dir = os.path.dirname(config_name)
            if not config_file_base_dir:
                config_file_base_dir = "."
            fn = config_name
            cfg = load(open(fn))
            if cfg == None: return {}
            for inc in cfg.get("IncludeTestSuite", []):
                if inc[0] == "/":
                    fn = inc
                else:
                    fn = config_file_base_dir + "/" + inc
                print "  Included test suite ->  " + fn
                inc_cfg = (load(open(fn)))
                for inc2 in inc_cfg.get("IncludeTestSuite", []):
                    if inc2[0] == "/":
                        fn = inc2
                    else:
                        fn = config_file_base_dir + "/" + inc2
                    print "    Included test suite ->  " + fn
                    inc_cfg.update(load(open(fn)))
                cfg.update(inc_cfg)
            return decode_metaconfig(cfg, cfg_script)

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
            if not isinstance(v, dict):
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

    def create_effective_config_file(self, override_cf="", default_cf=""):
        """
        Return the complete test suite file to be used for this test
        after it is folded in with the default configuration
        """

        if override_cf == "":
            override_cf=self.user_config_doc
        else:
            override_cf=self.load_config_file( override_cf )

        if default_cf == "":
            default_cf=self.default_config_doc
        else:
            default_cf=self.load_config_file( default_cf )

        # get a copy of the default configuration for a test 
        _, default_config = default_cf.items()[0]

        # then, for each new test entry (stanza) in the user_config_doc
        # merge with the default entry (overriding the defaults)
        new_dict = {}
        for test_id, v in override_cf.items():
            # only use "good" entries
            if isinstance(v, dict):
                if not TestEntry.check_valid(v):
                    print ", skipping stanza (%s) due to invalid entry" % test_id
                    continue
            tmp_config = default_config.copy()

            # merge the user dictionary with the default configuration. Tried
            # other dict methods ( "+", chain, update) and these did not work with nested dict.
            new_dict[test_id] = merge(tmp_config, override_cf[test_id])

        return new_dict

    def get_effective_config_file(self):
        return self.ecf

    def show_effective_config_file(self):
        """
        Display the effective config file
        """
        #ecf = self.get_effective_config_file()
        print json.dumps(self.ecf, sort_keys=True, indent=4)

    def extract_nested_tests( self, test_suite ):
        """
        This method should recursively check for the 'IncludeTestSuite' key in each
        successive test suite and expand it into a single test suite.
        """
        if not isinstance( test_suite, dict ):
            error_msg = "Loaded test suite is not well-formed."
            self.logger.error( error_msg )
            sys.exit(error_msg)
    
        ret_dict = {}
    
        if "IncludeTestSuite" in test_suite.keys():
            for testfile in test_suite['IncludeTestSuite']:
                if len(testfile) >= 5 and testfile[-5:] != ".yaml":
                    testfile += ".yaml"
                elif len(testfile) < 5:
                    testfile += ".yaml"
                try:
                    ret_dict[testfile[:-6]] = self.load_config_file(testfile)
                    tmp_dict = self.extract_nested_tests( ret_dict[testfile[:-6]] )
                    if tmp_dict != {}:
                        for testname, test in tmp_dict.iteritems():
                            ret_dict[testname] = test
                        del ret_dict[testfile[:-6]]
                except:
                    error_msg = "Test file included by 'IncludeTestSuite' key could not be loaded."
                    self.logger.error( error_msg )
                    sys.exit(error_msg)
    
        return ret_dict

    def find_expansions( self, test ):
        """
        This function will crawl through a test and try to find lists that need to be
        expanded into individual tests.
        """

        if not isinstance( test, dict ):
            error_msg = "Object provided to find_expansions function is not of type dict."
            self.logger.error( error_msg )
            sys.exit( error_msg )

        for t_key, t_val in test.iteritems():
            if isinstance( t_val, dict ):
                name, target = self.find_expansions( t_val )
                if target == ["empty"]:
                    return "empty", ["empty"]
                else:
                    ret_key = t_key + '.' + name
                    return ret_key, target
            elif isinstance( t_val, list ) and len( t_val ) != 0:
                return t_key, t_val
            else:
                return "empty", ["empty"]

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
