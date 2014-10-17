#!python
"""  Implementation of Moab Job Controller  """

import sys
import os
import subprocess
import re
from basejobcontroller import JobController


class MoabJobController(JobController):
    """ class to run a job using Moab """

    def is_moab_system(self):
        if os.path.isfile("/etc/toss-release"):
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
        if self.configs['moab']['queue']:
            msub_cmd += self.configs['moab']['queue'] + " "

        # add test name
        msub_cmd += "-N " + self.name + " "

        # get time limit, if specified
        time_lim = self.configs['moab']['time_limit']

        # get target segment, if specified
        ts = ''
        if self.configs['moab']['target_seg']:
            ts = self.configs['moab']['target_seg']

        reservation = ''
        if self.configs['moab']['reservation']:
            reservation = self.configs['moab']['reservation']

        # accounting file? or just log it?

        # variation passed as arg0 - nodes, arg1, ppn
        nnodes = str(self.job_variation[0])
        ppn = str(self.job_variation[1])

        self.logger.info(self.lh + " : nnodes=" + nnodes)

        pes = int(ppn) * int(nnodes)

        self.logger.info(self.lh + " : npes=" + str(pes))
        os.environ['GZ_PESPERNODE'] = ppn
        os.environ['PV_PESPERNODE'] = ppn

        os.environ['GZ_NNODES'] = nnodes
        os.environ['PV_NNODES'] = nnodes
        print "<nnodes> " + nnodes

        os.environ['PV_NPES'] = str(pes)
        os.environ['GZ_NPES'] = os.environ['PV_NPES']
        print "<npes> " + str(pes)

        # create working space here so that each msub run gets its own
        self.setup_working_space()

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # store some info into ENV variables that jobs may need to use later on.
        self.setup_job_info()

        # setup unique Moab stdout and stderr file names
        # Handle differences between moab-slurm, moab-cle, etc. ??
        se = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stderr"
        so = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stdout"
        msub_cmd += "-o " + so + " -e " + se + " "

        msub_cmd += "-l nodes=" + nnodes + ",walltime=" + time_lim
        if ts:
            msub_cmd += ",feature=" + ts
        if reservation:
            msub_cmd += ",advres=" + reservation

        run_cmd = os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        os.environ['USER_CMD'] = run_cmd

        msub_cmd += " " + os.environ['PVINSTALL'] + "/PAV/modules/moab_job_handler.py"

        if self.is_moab_system():
            self.logger.info(self.lh + " : " + msub_cmd)
            # call to invoke real Moab command
            output = subprocess.check_output(msub_cmd, shell=True)
            # Finds the jobid in the output from msub. The job id can either
            # be just a number or Moab.number.
            match = re.search("^((Moab.)?(\d+))[\r]?$",  output, re.IGNORECASE|re.MULTILINE)
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
    
    # instantiate a class to handle the config files
    mjc = MoabJobController()

    sys.exit()