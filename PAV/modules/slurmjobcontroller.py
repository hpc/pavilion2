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


"""  Implementation of Slurm Job Controller
"""

import sys
import os
import subprocess
#import re
from PAV.modules.basejobcontroller import JobController, JobException
from PAV.modules.helperutilities import which


class SlurmJobController(JobController):
    """ class to run a job using Slurm """

    @staticmethod
    def is_slurm_system():
        if which("sinfo") is not None:
            return True
        return False

    # .. some setup and let the run command fly ...
    def start(self):

        # Stuff any buffered output into the output file now
        # so that the the order doesn't look all mucked up
        sys.stdout.flush()

        slurm_cmd = "sbatch"

        # specified nodenames
        length_of_node_list = -1
        node_list = ''
        if 'node_list' in self.configs['slurm'] and self.configs['slurm']['node_list']:
            length_of_node_list = 0
            node_list = str(self.configs['slurm']['node_list'])
            slurm_cmd += ' -w ' + node_list
            # need the count of nodes or sbatch complains, you can use nnodes internally though

            # does it use hostlist representation?
            if "[" in node_list and "]" in node_list:
                for sublist in node_list.split("[")[1].split("]")[0].split(","):
                    # is it a range?
                    if "-" in sublist:
                        length_of_node_list = length_of_node_list + \
                                              int(sublist.split("-")[1]) - \
                                              int(sublist.split("-")[0]) + 1
                    else:
                        length_of_node_list += 1
            else:
                length_of_node_list = len(node_list.split(","))
            print "<node_list> " + node_list + " = " + str(length_of_node_list) + " nodes"

        # add test name
        slurm_cmd += " -J " + self.name

        # reservation
        if "reservation" in self.configs['slurm'] and self.configs['slurm']['reservation']: 
            reservation = self.configs['slurm']['reservation']
            slurm_cmd += " --reservation=" + reservation
            print "<reservation> " + reservation
            self.logger.info(self.lh + " : reservation=" + reservation)
            
        # constraint
        if "constraint" in self.configs['slurm'] and self.configs['slurm']['constraint']: 
            constraint = self.configs['slurm']['constraint']
            slurm_cmd += " --constraint=" + constraint
            print "<constraint> " + constraint
            self.logger.info(self.lh + " : constraint=" + constraint)

        # get time limit, if specified
        if "time_limit" in self.configs['slurm'] and self.configs['slurm']['time_limit']: 
            try:
                time_lim = self.configs['slurm']['time_limit']
                self.logger.info(self.lh + " : time limit = " + time_lim)

                slurm_cmd += " -t " + time_lim
            except TypeError:
                self.logger.info(self.lh + " Error: time limit value, " +
                                 "test suite entry may need quotes")
                print " Error: time limit value, test suite entry may need quotes"
                raise


        # add in a target segment (partition in Slurm vernacular), if specified
        if 'target_seg' in self.configs['slurm'] and self.configs['slurm']['target_seg']:
            slurm_cmd += " -p " + str(self.configs['slurm']['target_seg'])
            print "<segName> " + str(self.configs['slurm']['target_seg'])
        else:
            print "<segName> DEFAULT"

        nnodes = str(self.configs["slurm"]["num_nodes"])
        os.environ['PV_NNODES'] = nnodes
        print "<nnodes> " + nnodes
        self.logger.info(self.lh + " : nnodes=" + nnodes)

        ppn = str(self.configs["slurm"]["procs_per_node"])
        os.environ['PV_PESPERNODE'] = ppn
        print "<ppn> " + ppn
        self.logger.info(self.lh + " : ppn=" + ppn)

        pes = int(ppn) * int(nnodes)
        os.environ['PV_NPES'] = str(pes)
        print "<npes> " + str(pes)
        self.logger.info(self.lh + " : npes=" + str(pes))

        # number of nodes to allocate must be == length of node list
        if not (length_of_node_list == -1 or length_of_node_list == int(nnodes)):
            print "Error: node_list and num_nodes do not agree!"

        if not node_list:
            slurm_cmd += " -N " + nnodes

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # setup unique Slurm stdout and stderr file names
        se = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/slurm-%j.out"
        so = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/slurm-%j.out"
        slurm_cmd += " -o " + so + " -e " + se

        run_cmd = os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        os.environ['USER_CMD'] = run_cmd

        # Executable is slurm_job_handler.py which is just the wrapper to call the
        # actual application executable. Look at moab_job_handler.py to see what is
        # being collected and printed to the output log.
        slurm_cmd += " " + os.environ['PVINSTALL'] + "/PAV/modules/slurm_job_handler.py"

        if SlurmJobController.is_slurm_system():

            self.logger.info(self.lh + " : " + slurm_cmd)
            # call to invoke real Slurm command

            try:
                output = subprocess.check_output(slurm_cmd, shell=True,
                                                 stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
                self.logger.info(self.lh + " : sbatch exit status:" +
                                 str(e.returncode))
                self.logger.info(self.lh + " : sbatch output:" + e.output)
                raise JobException(e.returncode, e.output)

            # Finds the jobid in the output.
            jid = 0
            if not output is None and "job" in output:
                # "Submitted batch job JID"
                jid = output.split(" ")[3]
            print "<JobID> " + str(jid)

        else:
            # fake-out section to run on basic unix system
            fake_job_cmd = os.environ['PVINSTALL'] + \
                           "/PAV/modules/slurm_job_handler.py"
            p = subprocess.Popen(fake_job_cmd, stdout=self.job_log_file,
                                 stderr=self.job_log_file, shell=True)
            # wait for the subprocess to finish
            (output, errors) = p.communicate()
            if p.returncode or errors:
                print "Error: something went wrong!"
                print [p.returncode, errors, output]
                self.logger.info(self.lh + " run error: " + errors)

    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
