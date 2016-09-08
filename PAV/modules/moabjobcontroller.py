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


"""  Implementation of Moab Job Controller  """

import sys
import os
import subprocess
import re
from basejobcontroller import JobController
from helperutilities import which


class MoabJobController(JobController):
    """ class to run a job using Moab """

    def setup_msub_cmd(self, user_script):
        """
        create dynamic moab_job_handler script if users script contains msub
        DW directives.
        """

        fixed_cmd = os.environ['PVINSTALL'] + "/PAV/modules/moab_job_handler.py"
        my_moab_wrapper_text = ""

        # if DataWarp directives exist in the user script build new wrapper script on the fly
        with open(user_script) as f:
            match = re.findall('^#DW\s.+', f.read(), re.MULTILINE)
            if match:
                first_line = "#!/usr/bin/env python"
                my_moab_wrapper_text += first_line + "\n"
                for md in match:
                    self.logger.info(self.lh + " : adding directive: " + str(md))
                    my_moab_wrapper_text += md + "\n"

                with open(fixed_cmd, 'r') as fc:
                    for li in fc:
                        if 'Template' in li:
                            for next_line in fc:  # here are the lines we want
                                my_moab_wrapper_text += next_line

                my_home_dir = os.path.expanduser("~")
                my_moab_wrapper = my_home_dir + "/my_moab_wrapper" + ".py"
                mw = open(my_moab_wrapper, "w")
                mw.write(my_moab_wrapper_text)
                mw.close()
                dyn_cmd = " " + my_moab_wrapper

            else:
                dyn_cmd = fixed_cmd

        return dyn_cmd


    @staticmethod
    def is_moab_system():
        #if os.path.isfile("/etc/toss-release"):
        if which("mdiag"):
            return True
        else:
            return False

    # .. some setup and let the msub command fly ...
    def start(self):

        # Stuff any buffered output into the output file now
        # so that the the order doesn't look all mucked up
        sys.stdout.flush()

        msub_cmd = "msub -V "

        # handle optionally specified queue
        if 'queue' in self.configs['moab'] and self.configs['moab']['queue']:
            msub_cmd += "-q " + self.configs['moab']['queue'] + " "

        # add test name
        msub_cmd += "-N " + self.name + " "

        # get time limit, if specified
        time_lim = ''
        try:
            time_lim = str(self.configs['moab']['time_limit'])
            self.logger.info(self.lh + " : time limit = " + time_lim)
        except TypeError:
            self.logger.info(self.lh + " Error: time limit value, test suite entry may need quotes")

        # get target segment, if specified
        ts = ''
        if 'target_seg' in self.configs['moab'] and self.configs['moab']['target_seg']:
            ts = self.configs['moab']['target_seg']

        reservation = ''
        if 'reservation' in self.configs['moab'] and self.configs['moab']['reservation']:
            reservation = self.configs['moab']['reservation']

        node_list = ''
        if 'node_list' in self.configs['moab'] and self.configs['moab']['node_list']:
            node_list = self.configs['moab']['node_list']

        machine_type = ''
        if 'machine_type' in self.configs['moab'] and self.configs['moab']['machine_type']:
            machine_type = self.configs['moab']['machine_type']
        # ++ PV_MACHINETYPE : The type of machine requested from moab
        os.environ['PV_MACHINETYPE'] = machine_type

        os_type = ''
        if 'os' in self.configs['moab'] and self.configs['moab']['os']:
            os_type = self.configs['moab']['os']
        # ++ PV_OS : The os type requested from moab
        os.environ['PV_OS'] = os_type

        # accounting file? or just log it?

        # variation passed as arg0 - nodes, arg1 - ppn
        nnodes = str(self.configs['moab']['num_nodes'])
        #nnodes = str(self.job_variation[0])
        #ppn = str(self.job_variation[1])
        ppn = str(self.configs['moab']['procs_per_node'])

        self.logger.info(self.lh + " : nnodes=" + nnodes)
        self.logger.info(self.lh + " : ppn=" + ppn)
        self.logger.info(self.lh + " : args=" + str(self.configs['run']['test_args']))

        pes = int(ppn) * int(nnodes)
        self.logger.info(self.lh + " : npes=" + str(pes))

        # ++ PV_PESPERNODE : Number of cores per node
        os.environ['GZ_PESPERNODE'] = ppn
        os.environ['PV_PESPERNODE'] = ppn

        # ++ PV_NNODES : Number of nodes allocated for this job
        os.environ['GZ_NNODES'] = nnodes
        os.environ['PV_NNODES'] = nnodes
        print "<nnodes> " + nnodes

        # ++ PV_NPES : Number of pe's allocated for this job
        os.environ['PV_NPES'] = str(pes)
        os.environ['GZ_NPES'] = os.environ['PV_NPES']
        print "<npes> " + str(pes)

        # create working space here so that each msub run gets its own
        #self.setup_working_space()

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # store some info into ENV variables that jobs may need to use later on.
        self.setup_job_info()

        # setup unique Moab stdout and stderr file names
        # Handle differences between moab-slurm, moab-cle, etc. ??
        # ++ PV_JOB_RESULTS_LOG_DIR : Path where results for this job are placed
        se = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stderr"
        so = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stdout"
        msub_cmd += "-o " + so + " -e " + se + " "

        if node_list:
            msub_cmd += "-l nodes=" + node_list
        else:
            msub_cmd += "-l nodes=" + nnodes
        if machine_type:
            msub_cmd += ":" + machine_type
        if os_type:
            msub_cmd += ",os=" + os_type
        if time_lim:
            msub_cmd += ",walltime=" + time_lim
        if ts:
            msub_cmd += ",feature=" + ts
        if reservation:
            msub_cmd += ",advres=" + reservation

        # ++ PV_RUNHOME : Path where this job is run from
        run_cmd = os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        os.environ['USER_CMD'] = run_cmd

        # msub_cmd += " " + os.environ['PVINSTALL'] + "/PAV/modules/moab_job_handler.py"

        if MoabJobController.is_moab_system():
            msub_wrapper_script = self.setup_msub_cmd(run_cmd)
            msub_cmd += " " + msub_wrapper_script
            self.logger.info(self.lh + " : " + msub_cmd)
            # call to invoke real Moab command
            try:
               output = subprocess.check_output(msub_cmd, shell=True, stderr=subprocess.STDOUT)
            except subprocess.CalledProcessError as e:
               self.logger.info(self.lh + " : msub exit status:" + str(e.returncode))
               print "msub exit status:" + str(e.returncode)
               self.logger.info(self.lh + " : msub output:" + e.output)
               print "msub output:" + e.output
               sys.stdout.flush()
               raise

            # Finds the jobid in the output from msub. The job id can either
            # be just a number or Moab.number.
            match = re.search("^((Moab.)?(\d+))[\r]?$",  output, re.IGNORECASE | re.MULTILINE)
            jid = 0
            if match.group(1):
                jid = match.group(1)
            print "<JobID> " + str(jid)

        else:
            # fake-out section to run on basic unix system
            fake_job_cmd = os.environ['PVINSTALL'] + "/PAV/modules/moab_job_handler.py"
            p = subprocess.Popen(fake_job_cmd, stdout=self.job_log_file, stderr=self.job_log_file, shell=True)
            # wait for the subprocess to finish
            (output, errors) = p.communicate()
            if p.returncode or errors:
                print "Error: something went wrong!"
                print [p.returncode, errors, output]
                self.logger.info(self.lh + " run error: " + errors)

    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
