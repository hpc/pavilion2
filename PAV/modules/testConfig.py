#!/usr/bin/env python

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
            else:
                result[key] = merge(value, obj_2[key])
        for key, value in obj_2.iteritems():
            if key not in obj_1:
                result[key] = value
        return result
    if isinstance(obj_1, list) and isinstance(obj_2, list):
        return obj_1 + obj_2
    return obj_2


class YamlTestConfig():
    """
    class to manipulate test suite config files being used
    """

    def __init__(self, ucf="../test_suites/user_test_config.yaml"):

        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pth.' + my_name)

        # Unless defined otherwise in the user's test suite config file the 
        # default config file is found in the same directory.
        test_suite_dir = os.path.dirname(os.path.realpath(ucf)) + "/"
        self.dcf = test_suite_dir + "default_test_config.yaml"

        self.user_config_doc = self.load_config_file(ucf)
        print "User testSuite -> " + ucf

        if "DefaultTestSuite" in self.user_config_doc:
            df = self.user_config_doc['DefaultTestSuite']
            if "/" not in df:
                self.dcf = test_suite_dir + df
            else:
                self.dcf = df
        print "Default testSuite -> " + self.dcf
        self.logger.info('Using default test config file: %s ' % self.dcf)

        self.default_config_doc = self.load_config_file(self.dcf)
        self.ecf = self.get_effective_config_file()

    def load_config_file(self, config_name):
        """
        Attempt to load a configuration file by the given name. Returns
        the loaded contents of the YAML file. On error should system
        exit since it doesn't make sense to continue with broken
        configuration.
        """
        try:
            with open(config_name) as config_file:
                file_contents = config_file.read()
                return load(file_contents)
        except EnvironmentError as err:
            error_message = "Error processing file: {0}\n".format(config_name)
            error_message += "I/O Error({0}): {1}.".format(err.errno, 
                                                           err.strerror)
            self.logger.error(error_message)
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

    def get_effective_config_file(self):
        """
        Return the complete test suite file to be used for this test
        after it is folded in with the default configuration
        """

        # get a copy of the default configuration for a test 
        dk, default_config = self.default_config_doc.items()[0]

        # then, for each new test/stanza in the user_config_doc
        # merge with the default entry (overriding the defaults)
        new_dict = {}
        for test_id, v in self.user_config_doc.items():
            # only use "good" entries
            if type(v) is dict:
                if not TestEntry.check_valid(v):
                    print ", invalid entry (%s) skipping!" % test_id
                    continue
            tmp_config = default_config.copy()

            # merge the user dictionary with the default configuration. Tried
            # other dict methods ( "+", chain, update) and these did not work with nested dict.
            new_dict[test_id] = merge(tmp_config, self.user_config_doc[test_id])

        return new_dict

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
