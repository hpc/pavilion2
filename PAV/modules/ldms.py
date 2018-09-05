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


""" plug-in that supports using the LDMS tool 
"""

import os
import subprocess
import datetime
import logging


class LDMS(object):

    def __init__(self, my_te):
        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pav.' + my_name)
        self.logger.info('initialize ' + my_name + ' to run: ')

        self.pid = str(os.getpid())
        self.lh = my_name

        params = my_te.get_values()
        self.name = my_te.get_name()
        self.install_dir = str(params['ldms']['install_dir'])
        self.start_cmd = str(params['ldms']['start_cmd'])
        self.output_dir_root = str(params['ldms']['output_dir_root'])
        self.freq = params['ldms']['freq']
        self.metric_list = str(params['ldms']['metric_list'])

        self.output_dir = self.create_output_dir()
        self.build_start_cmd()

    def create_output_dir(self):
        # This dir must be created before LDMS can start and should
        # be unique so that each new test run does not stomp on
        # existing data from a prior one.

        sub_dir = self.name + "-" + datetime.datetime.now().strftime('%m-%d-%YT%H:%M:%S:%f')
        if "HOME" in self.output_dir_root:
            root = os.environ['HOME']
        else:
            root = self.output_dir_root
        output_dir = root + "/ldmsData/" + sub_dir

        self.logger.info(self.lh + " Make metrics directory: " + output_dir)
        try:
            os.umask(0o002)
            os.makedirs(output_dir, 0o755)
        except OSError:
            print " Error creating metrics directory : \n\t" + output_dir
            self.logger.info(self.lh + " Error creating metrics directory : \n\t" + output_dir)
            output_dir = ''

        print "Created ldms metrics dir: " + output_dir

        os.environ['LDMS_OUTPUT_DIR'] = output_dir
        return output_dir

    def build_start_cmd(self):
        full_cmd = self.install_dir + "/" + self.start_cmd
        full_cmd += " -f " + str(self.freq)
        full_cmd += " -m " + self.metric_list
        full_cmd += " -s " + self.output_dir
        os.environ['LDMS_START_CMD'] = full_cmd

    # define some static methods for LDMS job control

    @staticmethod
    def start():
        # start and don't wait. Report success or fail in the log(s).
        outfile = os.environ['LDMS_OUTPUT_DIR'] + "/ldms.out"
        print "  starting LDMS with: \n    " + os.environ['LDMS_START_CMD']

        text_file = open(outfile, "w")
        try:
            subprocess.Popen(os.environ['LDMS_START_CMD'], stdout=text_file,
                             stdin=open(os.devnull), shell=True)
        except subprocess.CalledProcessError as e:
            ret = e.returncode
            if ret in (1, 2):
                print("the command failed")
            elif ret in (3, 4, 5):
                print("the command failed very much")

    @staticmethod
    def status(jid):
        pass

    @staticmethod
    def stop(jid):
        pass

if __name__ == "__main__":
    print LDMS.__doc__
