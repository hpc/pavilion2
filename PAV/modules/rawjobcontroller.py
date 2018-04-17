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


"""  Implementation raw Job Control mechanism  """

import sys
import os
import platform
import subprocess
from PAV.modules.basejobcontroller import JobController


class RawJobController(JobController):
    """ class to run a test using no scheduler or special launcher """

    def start(self):

        # create own unique working space for this run
        #self.setup_working_space()

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # store some info into ENV variables that jobs may need to use later on.
        self.setup_job_info()

        # what nodes(s) are this job running on...
        nodes = platform.node().partition('.')[0]
        os.environ['PV_NODES'] = nodes
        os.environ['GZ_NODES'] = os.environ['PV_NODES']
        print "<nodes> " + nodes + "\n"

        self.logger.info(self.lh + " : args=" + str(self.configs['run']['test_args']))

        # build the exact command to run
        cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + \
            os.environ['PVINSTALL'] + "/PAV/scripts/mytime ./" + self.configs['run']['cmd']
        print "\n ->  RawJobController: invoke %s" % cmd

        # Get any buffered output into the output file now
        # so that the the order doesn't look all mucked up
        sys.stdout.flush()

        # Invoke the cmd and send the output to the file setup when
        # the object was instantiated

        self.logger.info(self.lh + " run: " + cmd)
        p = subprocess.Popen(cmd, stdout=self.job_log_file, stderr=self.job_log_file, shell=True)
        # wait for the subprocess to finish
        output, errors = p.communicate()

        if p.returncode or errors:
            print "Error: something went wrong!"
            print [p.returncode, errors, output]
            self.logger.info(self.lh + " run error: " + errors)

        # The post_complete file needs to be placed in the results dir
        # for Gazebo compatibility
        pcf = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/post_complete"
        text_file = open(pcf, "w")
        text_file.write("{}\n".format("command complete"))
        self.run_epilog()
        text_file.write("{}\n".format("epilog complete"))
        self.cleanup()
        text_file.write("{}\n".format("cleanup complete"))
        text_file.close()

        print "<end>", self.now()

        # The trend_data file needs to be placed in the results dir
        # for Gazebo compatibility
        JobController.process_trend_data()
    
# this gets called if it's run as a script/program
if __name__ == '__main__':

    sys.exit()
