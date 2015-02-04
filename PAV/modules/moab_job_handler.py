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


"""
# Functions similar to setUpandRun in Gazebo.
# Application that is called by msub.
"""

import sys
import os
from subprocess import Popen, PIPE
import subprocess
import shutil
import platform
import datetime

newpath = os.environ['PVINSTALL'] + "/PAV/modules"
sys.path.append(newpath)
from basejobcontroller import JobController
from ldms import LDMS


def now():
    return " " + datetime.datetime.now().strftime("%m-%d-%YT%H:%M:%S")

from contextlib import contextmanager
@contextmanager
def stdout_redirected(new_stdout):
    save_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield None
    finally:
        sys.stdout = save_stdout


def get_moab_node_list():

    if "SLURM_JOBID" in os.environ:
        os.environ['PV_JOBID'] = os.environ.get("SLURM_JOBID")
        output = subprocess.check_output(os.environ['PVINSTALL'] + "/PAV/scripts/getSLURMNodeList", shell=True)
        nodes = output.replace('\n', " ")
    elif "PBS_JOBID" in os.environ:
        output = subprocess.check_output(os.environ['PVINSTALL'] + "/PAV/scripts/getCLENodeList", shell=True)
        nodes = output.replace('\n', " ")
    else:
        nodes = platform.node()
    return str(nodes)


def main():
    """
      Routine called by msub that calls the user's job script/program.
      Will also start LDMS if requested.
    """
    cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + \
        os.environ['PVINSTALL'] + "/PAV/scripts/mytime " + os.environ['USER_CMD']

    nodes = get_moab_node_list()
    os.environ['PV_NODES'] = nodes
    os.environ['GZ_NODES'] = os.environ['PV_NODES']
    job_log_file = os.environ["PV_JOB_RESULTS_LOG"]

    with open(job_log_file, 'a') as lf:
        with stdout_redirected(lf):

            #redirect STDERR to the same file
            sys.stderr = lf

            print "<nodes> " + nodes + "\n"
            print "moab_job_handler: "

            # start LDMS here if requested!  The start command ought to be
            # defined, so let's go!
            try:
                if os.environ['LDMS_START_CMD']:
                    print "start ldms! "
                    LDMS.start()
            except KeyError, e:
                #print 'I got a KeyError - no: "%s"' % str(e)
                pass

            print "  start job with: \n    " + cmd
            lf.flush()

            # Call the command that runs the users test/job
            # This works with job_out_file = /users/cwi/mystdout
            #subprocess.call(cmd1, stdout=job_out_file, shell=True)

            subprocess.call(cmd, stdout=lf, stderr=lf, shell=True)

            # The post_complete file needs to be placed in the results dir
            # for Gazebo compatibility
            pcf = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/post_complete"
            text_file = open(pcf, "w")
            text_file.write("{}\n".format("command complete"))
            JobController.run_epilog()
            text_file.write("{}\n".format("epilog complete"))
            JobController.cleanup()
            text_file.write("{}\n".format("cleanup complete"))
            text_file.close()

            print "<end>", now()
            lf.flush()

            # The trend_data file needs to be placed in the results dir
            # for Gazebo compatibility
            JobController.process_trend_data()


# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
