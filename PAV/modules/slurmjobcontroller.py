#!python
"""  Implementation of Slurm Job Controller

     **  Just a hacked up version of Moab Job controller for now,
     needs real work from knowledgeable Slurm person. Thus, some
     of the slurm_cmd arguments may or may not make sense.

     Environment vars that start with PV_ and any print
     statements with "<>" need to be left in, but with
     appropriate values, of course. These items will be
     added to the job output log file and are needed by
     Pavilion for job analysis.

"""

import sys
import os
import subprocess
import re
from basejobcontroller import JobController
from helperutilities import which


class SlurmJobController(JobController):
    """ class to run a job using Slurm """

    @staticmethod
    def is_slurm_system():
        if which("sinfo"):
            return True
        else:
            return False

    # .. some setup and let the run command fly ...
    def start(self):

        # Stuff any buffered output into the output file now
        # so that the the order doesn't look all mucked up
        sys.stdout.flush()

        slurm_cmd = " "

        # handle optionally specified queue
        if self.configs['slurm']['queue']:
            slurm_cmd += self.configs['slurm'][''] + " "

        # add test name
        slurm_cmd += "-N " + self.name + " "

        # get time limit, if specified
        time_lim = self.configs['slurm']['']

        # get target segment, if specified
        ts = ''
        if self.configs['slurm']['target_seg']:
            ts = self.configs['slurm']['target_seg']

        reservation = ''
        if self.configs['slurm']['reservation']:
            reservation = self.configs['slurm']['reservation']

        # variation passed as arg0 - nodes, arg1, ppn
        nnodes = str(self.job_variation[0])
        ppn = str(self.job_variation[1])

        self.logger.info(self.lh + " : nnodes=" + nnodes)

        pes = int(ppn) * int(nnodes)

        self.logger.info(self.lh + " : npes=" + str(pes))
        os.environ['PV_PESPERNODE'] = ppn

        os.environ['PV_NNODES'] = nnodes
        print "<nnodes> " + nnodes

        os.environ['PV_NPES'] = str(pes)
        print "<npes> " + str(pes)

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # store some info into ENV variables that jobs may need to use later on.
        self.setup_job_info()

        # setup unique Slurm stdout and stderr file names
        se = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stderr"
        so = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stdout"
        slurm_cmd += "-o " + so + " -e " + se + " "

        slurm_cmd += "-l nodes=" + nnodes + ",walltime=" + time_lim
        if ts:
            slurm_cmd += ",feature=" + ts
        if reservation:
            slurm_cmd += ",advres=" + reservation

        run_cmd = os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        os.environ['USER_CMD'] = run_cmd

        slurm_cmd += " " + os.environ['PVINSTALL'] + "/PAV/modules/slurm_job_handler.py"

        if SlurmJobController.is_slurm_system():
            self.logger.info(self.lh + " : " + slurm_cmd)
            # call to invoke real Slurm command
            output = subprocess.check_output(slurm_cmd, shell=True)
            # Finds the jobid in the output from msub.
            match = re.search("^((Slurm.)?(\d+))[\r]?$",  output, re.IGNORECASE | re.MULTILINE)
            jid = 0
            if match.group(1):
                jid = match.group(1)
            print "<JobID> " + str(jid)

        else:
            # fake-out section to run on basic unix system
            fake_job_cmd = os.environ['PVINSTALL'] + "/PAV/modules/slurm_job_handler.py"
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