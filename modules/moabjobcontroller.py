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

        # init processes per node (ppn)
        ppn = self.configs['moab']['procs_per_node']
        if (type(ppn) is not str):
            ppn = str(ppn)

        os.environ['GZ_PESPERNODE'] = ppn
        os.environ['PV_PESPERNODE'] = ppn

        num_nodes = self.configs['moab']['num_nodes']
        if (type(num_nodes) is not str):
            num_nodes = str(num_nodes)
        num_nodes_list = num_nodes.split(",")

        self.logger.debug(num_nodes_list)

        # handle multiple node sizes
        for nnodes in num_nodes_list:

            os.environ['GZ_NNODES'] = nnodes
            os.environ['PV_NNODES'] = nnodes
            pes = int(nnodes) * int(ppn)
            os.environ['PV_NPES'] = str(pes)

            # create working space here so that each msub run gets its own
            self.setup_working_space()

            # setup unique Moab stdout and stderr file names
            # Handle differences between moab-slurm, moab-cle, etc. ??
            so = os.environ['PV_RUNHOME'] + "/drm.stderr"
            se = os.environ['PV_RUNHOME'] + "/drm.stdout"
            msub_cmd += "-o " + so + " -e " + se + " "

            msub_cmd += "-l nodes=" + nnodes + ",walltime=" + time_lim
            if ts:
                msub_cmd += ",feature=" + ts

            cmd =  os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
            os.environ['USER_CMD'] = cmd

            # msub this
            msub_cmd += " " + "./moab_job_handler"
            self.logger.info(msub_cmd)
            jid = "222222"

            self.logger.info("job id %s launched!" % jid)

    def cleanup(self):
        pass
    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    mjc = MoabJobController()

    sys.exit()
    
