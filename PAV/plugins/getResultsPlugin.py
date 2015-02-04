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


""" plugin that implements the get_results command
"""

import os
import sys
from yapsy.IPlugin import IPlugin
from testConfig import YamlTestConfig
import subprocess
import logging
#from testEntry import TestEntry


class GetResults(IPlugin):
    """ This implements the plugin, or command, to get a summary of
        test results.
    """

    logger = logging.getLogger(__name__)

    def __init__(self):
        my_name = self.__class__.__name__
        self.logger.info('created instance of plugin: %s' % my_name)


    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the the sub-command

    def add_parser_info(self, subparser):
        parser_gr = subparser.add_parser("get_results", help="summarize test results")
        # parser_gr.add_argument('testSuite', help='test-suite-config-file')
        parser_gr.add_argument('-s', nargs=1, metavar='<date>', help="start date (yyyy-mm-dd), default 15 days ago")
        parser_gr.add_argument('-S', nargs=1, metavar='<time>', help="start time (HH:MM:SS), default is at 00:00:00")

        parser_gr.add_argument('-e', nargs=1, metavar='<date>', help="end date (yyyy-mm-dd), default today")
        parser_gr.add_argument('-E', nargs=1, metavar='<time>', help="start time (HH:MM:SS), default is at 23:59:59")

        parser_gr.add_argument('-t', nargs=1, metavar='<string>', help="test name to match on")

        parser_gr.add_argument('-u', nargs=1, metavar='<segment_name>', help="target segment to match on")

        parser_gr.add_argument('-f', '--fail', help="locate/show failed test directories", action="store_true")
        parser_gr.add_argument('-i', '--inc', help="locate/show 'incomplete' test directories", action="store_true")
        parser_gr.add_argument('-p', '--pass', help="locate/show passing test directories", action="store_true")
        parser_gr.add_argument('-T', '--td', help="display trend data", action="store_true")
        parser_gr.add_argument('-v', '--verbose', help="show work", action="store_true")

        parser_gr.add_argument('-ts', nargs=1, metavar='<file>',
                               help="test suite to determine results path (root) from, defaults \
                                to default_test_config.yaml")

        parser_gr.add_argument('-bp', '--make-box-plots', action="store_true",
                               help='create box plots from the selected set of test results and trend data values')

        parser_gr.add_argument('-bl', '--make-baselines', action="store_true",
                               help='create base line averages from the selected set'
                                    ' of test results and trend data values')

        parser_gr.set_defaults(sub_cmds='get_results')
        return 'get_results'

    # Every plug-in (command) MUST have a method by the name "cmd".
    # It will be what is called when that command is selected.
    def cmd(self, args):

        if args['verbose']:
            print "Command args -> %s" % args

        # see if user wants to use a specified test_suite
        if args['ts']:
            dts = str(args['ts'][0])
        else:
            dts = os.getcwd() + "/" + "../test_suites" + "/default_test_config.yaml"

        tc = YamlTestConfig(dts)

        if args['verbose']:
            print "effective test suite configuration:"
            tsc = tc.get_effective_config_file()
            print tsc

        # *** need to handle ALL result locations here!
        res_loc_list = tc.get_result_locations()
        # print res_loc_list
        for results_dir in res_loc_list:
            #print "\nFor results location: %s " % results_dir
            os.environ['PV_RESULT_ROOT'] = results_dir

            try:
                if os.access(results_dir, os.R_OK) is False:
                    print "  Warning: results directory (%s) not readable, skipping" % results_dir
                    continue
            except Exception as ex:
                template = "An exception of type {0} occurred."
                print "No results 'root' directory defined in the test suite config file(s), exiting!"
                message = template.format(type(ex).__name__, ex.args)
                #print message
                sys.exit()

            # call something here that gets the results
            self.logger.debug('get_results from %s' % results_dir)
            # add in all the possible args
            # implement different shared Nix groups later, using gzshared for now
            bc = "/scripts/get_results -g gzshared"
            if args['pass']:
                bc += " -p "
            if args['fail']:
                bc += " -f "
            if args['verbose']:
                bc += " -v "
            if args['inc']:
                bc += " -i "
            if args['s']:
                bc += " -s " + args['s'][0]
            if args['S']:
                bc += " -S " + args['S'][0]
            if args['e']:
                bc += " -e " + args['e'][0]
            if args['E']:
                bc += " -E " + args['E'][0]
            if args['t']:
                bc += " -t " + args['t'][0]
            if args['u']:
                bc += " -u " + args['u'][0]
            if args['td']:
                bc += " -T "

            if args['make_box_plots']:
                plot_cmd = os.environ['PVINSTALL'] + "/PAV/modules/makeboxplots.py"
                gr_cmd = os.environ['PVINSTALL'] + "/PAV" + bc + " -T -l " + results_dir + " | " + plot_cmd
            elif args['make_baselines']:
                bl1_cmd = os.environ['PVINSTALL'] + "/PAV/modules/makebaselines.py"
                bl2_cmd = os.environ['PVINSTALL'] + "/PAV/scripts/mkBaselines"
                gr_cmd = os.environ['PVINSTALL'] + "/PAV" + bc + " -T -l " + results_dir + " | " +\
                    bl1_cmd + " | " + bl2_cmd
            else:
                gr_cmd = os.environ['PVINSTALL'] + "/PAV" + bc + " -l " + results_dir

            if args['verbose']:
                print "Using command:"
                print gr_cmd
            gr_output = subprocess.check_output(gr_cmd, shell=True)
            print "\n" + gr_output


if __name__ == "__main__":
    print GetResults.__doc__
