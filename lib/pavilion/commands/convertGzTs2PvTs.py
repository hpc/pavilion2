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


""" skeleton example plug-in that implements a new command 
"""

import sys
import os
import subprocess
import logging

import string
import shlex

from yapsy.IPlugin import IPlugin

my_dict = {
    'name:=': 'value1',
    'nodes:=': 'value2',
    'pes:=': 'value3',
    'tl:=': 'value4',
    'pl:=': 'value5',
    'count:=': 'value6',
    'pct:=': 'value7',
    'nl:=': 'value8'
}


class Switch(object):
    value = None

    def __new__(cls, value):
        cls.value = value
        return True


def case(*args):
    return any((arg == Switch.value for arg in args))


class gzts2pvtsPlugin(IPlugin):
    """ This is plugin 1 that implements the gzts2pvts command """

    def __init__(self):

        my_name = self.__class__.__name__

        # To log output from this class to to the
        # main (pav) log file you tack it's name onto the pav name space
        self.logger = logging.getLogger('pav.' + my_name)
        self.logger.info('created instance of plugin: %s' % my_name)

    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the this sub-command

    def add_parser_info(self, subparser): 
        parser_gzts2pvts = subparser.add_parser("gzts2pvts",
                                                help="convert Gazebo test suite to Pavilion test suite")
        parser_gzts2pvts.add_argument('-i', default='no_file',
                                      help='input file in Gazebo test suite format')
        parser_gzts2pvts.add_argument('-o', default='~/inputfile.yaml',
                                      help='output file or path')
        parser_gzts2pvts.add_argument('-d', default='~/testparentdirectory',
                                      help='Gazebo parent directory, will use GZHOME if defined')

        parser_gzts2pvts.set_defaults(sub_cmds='gzts2pvts')
        return 'gzts2pvts'

    # Every plugin class MUST have a method by the name "cmd"
    # It will get invoked when sub-command is selected
        
    def cmd(self, args):
        print "running gzts2pvts with:"
        print "args -> %s" % args
        
        # handle the count argument
        gzinputfile = args['i']
        pvoutputfile = args['o']
        testparentdir = args['d']

        # handle input case 1]
        #  no inputfile

        if gzinputfile == "no_file":
            print "Error: An input file is necessary, please provide one with the -i argument, exiting."
            sys.exit()

        # handle input case 2]
        #  no output file specified, use input-filename with .yaml extension in the home directory
        if pvoutputfile == "~/inputfile.yaml":
            out_dir = os.environ.get('HOME')    # why? because opening a file with ~/filename doesn't work
            pvoutputfile = out_dir + "/" + os.path.basename(gzinputfile) + ".yaml"

        elif os.path.isdir(pvoutputfile):
            out_dir = pvoutputfile
            pvoutputfile = out_dir + "/" + os.path.basename(gzinputfile) + ".yaml"

        elif os.path.isfile(pvoutputfile):
            pass  # we are good to go

        # handle input case 3]
        #  no testparentdirectory is specified.  Testparentdirectory is necessary to get
        #  locations of tests and to produce a run command from gzconfig file.
        #  The below will check GZHOME environment variable and use it if it is set, otherwise
        #  it will printout REQUIRED on lines where output cannot be determined.
        if testparentdir == "~/testparentdirectory":
            gzhome = os.environ.get('GZHOME')
            # print "gzhome is ", gzhome
            if gzhome:
                print "Using a test parent directory of " + gzhome
            else:
                testparentdir = "/REQUIRED"
                gzhome = testparentdir
                if args['verbose']:
                    print "Notice: GZHOME environment variable not defined "
                    print "Cannot determine a test parent directory, continuing."
        else:
            gzhome = testparentdir

        if args['verbose']:
            print "Converting %s Gazebo test suite " % gzinputfile
            print " to %s that's in Pavilion test suite format " % pvoutputfile

        try:
            gz_in_file = open(gzinputfile, 'r')
            pv_out_file = open(pvoutputfile, 'w')
        except IOError:
            print "Error: opening I/O file, exiting!"
            sys.exit()

# example gazebo input line:
# name:=mem-gf-bynuma nodes:=1 pes:=24  tl:=00:30:30 pl:="30 128 56 24 " count:=1 nl:=mu0121 pct:=20

# pavilion output format sample stanza for this test:
# mem-gf-bynuma-1:
#   name: mem-gf-bynuma
#   source_location: '/usr/projects/packages/prr/ATC-ml/test_exec/mem-gf-bynuma'
#   run:
#     cmd: 'runMemGf'
#     scheduler: moab
#     test_args: 30 128 56 24
#     count: 1
#   moab:
#     num_nodes: 1
#     procs_per_node: 24
#     time_limit: 00:30:30
#     node_list: mu0121
#     percent: 20

        emptyline = ""

        linenumber = 1
        for line in gz_in_file:
            # process only the lines that start with n (as in name:=)
            if line[0] == "n":
                num_nodes = 0
                procspernode = 0
                timelimit = 0
                nodelist = 0
                pctlist = 0

                # split the line into parts but preserve the ' ', necessary for parameter lists
                newline = shlex.split(line)
                for tagname in newline:
                    # split the already split line into keyvalue pairs with keysplit[0] being
                    #   the name and keysplit[1] being the value
                    keysplit = tagname.split(":=")
                    # use a switch statement to process the key value pairs
                    while Switch(keysplit[0]):
                        if case('name'):
                            print >> pv_out_file, emptyline
                            testline = keysplit[1] + "-" + str(linenumber) + ":"
                            print >> pv_out_file, testline
                            testline = "  name: " + keysplit[1]
                            print >> pv_out_file, testline
                            srclocation = "  source_location: '" + gzhome + "/test_exec/" + keysplit[1] + "'"
                            if gzhome:
                                print >> pv_out_file, srclocation
                            else:
                                print >> pv_out_file, "source_location: REQUIRED"
                                if args['verbose']:
                                    print "source location could not be found, replace REQUIRED text in output file"

                            print >> pv_out_file, '  run:'
                            getrunscript = "grep CMD " + gzhome + "/test_exec/" + keysplit[1] +\
                                           "/gzconfig | awk '{if (NR == 1 ) print $3}'  "
                            # print "Get Runscript is ", getrunscript
                            #  p = subprocess.Popen(getrunscript, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            #  shell=True)
                            p = subprocess.Popen(getrunscript, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                                 shell=True)
                            # p = subprocess.Popen(getrunscript, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            #  shell=False)
                            code = p.wait()
                            output = p.stdout.read()
                            # print "output from get cmd ", output
                            newcmd = string.replace(output, '"', '')
                            newcmd = string.replace(newcmd, ';', '\'')
                            newcmd = string.replace(newcmd, '\n', '')
                            testline = "    cmd: '" + newcmd
                            if newcmd != "":
                                print >> pv_out_file, testline
                            else:
                                print >> pv_out_file, "    cmd: REQUIRED"
                                if args['verbose']:
                                    print "run command could not be found, replace REQUIRED text output file"

                            print >> pv_out_file, "    scheduler: moab"
                            # print "in case ", keysplit[0], " is ", keysplit[1]
                            break
                        if case('nodes'):
                            numnodesline = "    num_nodes: " + keysplit[1]
                            latestprocs = int(keysplit[1])
                            num_nodes = 1
                            break
                        if case('pes'):
                            ppernode = int(keysplit[1]) / latestprocs
                            procspernodeline = "    procs_per_node: " + str(ppernode)
                            procspernode = 1
                            break
                        if case('tl'):
                            timeline = "    time_limit: " + keysplit[1]
                            timelimit = 1
                            break
                        if case('pl'):
                            testline = "    test_args: " + keysplit[1]
                            print >> pv_out_file, testline
                            break
                        if case('count'):
                            testline = "    count: " + keysplit[1]
                            print >> pv_out_file, testline
                            break
                        if case('nl'):
                            nodeline = "    node_list: " + keysplit[1]
                            nodelist = 1
                            # print >> pv_out_file, testline
                            break
                        if case('pct'):
                            pctline = "    percent: " + keysplit[1]
                            pctlist = 1
                            break

                        print " Case ", keysplit[0], " not implemented "
                        break

                        # Only the name key value pair produces file output above, the rest need to be checked and
                        #  printed in order print out the remaining 5 tags in order so they fall under the
                        #  moab: section. "

                print >> pv_out_file, '  moab:'
                if num_nodes == 1:
                    print >> pv_out_file, numnodesline
                if procspernode == 1:
                    print >> pv_out_file, procspernodeline
                if timelimit == 1:
                    print >> pv_out_file, timeline
                if nodelist == 1:
                    print >> pv_out_file, nodeline
                if pctlist == 1:
                    print >> pv_out_file, pctline

            linenumber += 1

        gz_in_file.close()
        pv_out_file.close()

        print "\nNew Test Suite written to -> " + pvoutputfile


if __name__ == "__main__":
    print gzts2pvtsPlugin.__doc__
