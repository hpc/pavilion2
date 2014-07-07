#!python
"""  Implementation of Moab Job Controller  """

import sys, os
import subprocess
from basejobcontroller import BaseJobController
import time



class MoabJobController(BaseJobController):
    """ class to run/stop a job using Moab """


    # Invoke the correct way of running the job/test as defined in the
    # tests config entry.
    def start(self):

        # Get any buffered output into the output file now
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

        # accounting file? or just log it?

        ppn = str(self.configs['eff_npes'])
        os.environ['GZ_PESPERNODE'] = ppn
        os.environ['PV_PESPERNODE'] = ppn

        nnodes = str(self.configs['eff_nnodes'])
        os.environ['GZ_NNODES'] = nnodes
        os.environ['PV_NNODES'] = nnodes
        print "<nnodes> " + nnodes

        pes = int(nnodes) * int(ppn)
        os.environ['PV_NPES'] = str(pes)
        print "<npes> " + str(pes)

        # create working space here so that each msub run gets its own
        self.setup_working_space()

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # setup unique Moab stdout and stderr file names
        # Handle differences between moab-slurm, moab-cle, etc. ??
        so = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stderr"
        se = os.environ['PV_JOB_RESULTS_LOG_DIR'] + "/drm.stdout"
        msub_cmd += "-o " + so + " -e " + se + " "

        msub_cmd += "-l nodes=" + nnodes + ",walltime=" + time_lim
        if ts:
            msub_cmd += ",feature=" + ts

        cmd =  os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        os.environ['USER_CMD'] = cmd

        # invoke msub here
        msub_cmd += " " + "./moab_job_handler"
        self.logger.info(self.lh + " : " + msub_cmd)

        self.logger.info(self.lh + " Dummy job is launched!")

    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    mjc = MoabJobController()

    sys.exit()
    
