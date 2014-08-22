#!python

""" plugin that implements the get_results command
"""

import os
import sys
from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
import subprocess
import logging


class GetResults(IPlugin):
    """ This implements the plugin, or command, to get a summary of
        test results.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        my_name = self.__class__.__name__
        #self.logger = logging.getLogger('pth.' + my_name)
        #self.logger = logging.getLogger( __name__)
        self.logger.info('created instance of plugin: %s' % my_name)

    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the the sub-command

    def add_parser_info(self, subparser): 
        parser_gr = subparser.add_parser("get_results", help="summarize test results")
        #parser_gr.add_argument('testSuite', help='test-suite-config-file')
        parser_gr.add_argument('-s', nargs=1, help="default start date (yyyy-mm-dd), default 15 days ago")
        parser_gr.add_argument('-S', nargs=1, help="default start time (HH:MM:SS), default is at 00:00:00")

        parser_gr.add_argument('-e', nargs=1, help="default end date (yyyy-mm-dd), default today")
        parser_gr.add_argument('-E', nargs=1, help="default start time (HH:MM:SS), default is at 23:59:59")

        parser_gr.add_argument('-t', nargs=1, help="test name string to match")

        parser_gr.add_argument('-f', '--fail', help="locate failed test directories", action="store_true")
        parser_gr.add_argument('-i', '--inc', help="locate 'incomplete' test directories", action="store_true")
        parser_gr.add_argument('-p', '--pass', help="locate passing test directories", action="store_true")

        parser_gr.add_argument('-T', nargs=1, help="display trend data")

        parser_gr.add_argument('-ts', nargs=1, help="test suite to acquire results path, defaults to default_test_config.yaml")

        parser_gr.set_defaults(sub_cmds='get_results')
        return 'get_results'

    # Every plug-in(command) class MUST have a method by the name "cmd"
    # so that it can called when its sub-command is selected
        
    def cmd(self, args):

        if args['verbose']:
            print "Command args -> %s" % args

        # see if user wants to use a specified test_suite
        if args['ts']:
            dts = str(args['ts'][0])
        else:
            dts = os.getcwd() + "/" + "../test_suites" + "/default_test_config.yaml"

        tc = YamlTestConfig(dts)
        tsc = tc.get_effective_config_file()

        if args['verbose']:
            print "effective test suite configuration:"
            print tsc

        # look for the test result location
        for name, params in tsc.iteritems():

            if "DefaultTestSuite" in name:
                continue

            if params['results']['root']:
                print "\n let's use the results found in :"
                result_location = params['results']['root']
                print result_location
                break  # use the first one found for now
            else:
                print "No results location found from test suite config file, exiting!"
                sys.exit()

        # call something here that gets the results


if __name__ == "__main__":
    print GetResults.__doc__
