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

        cmd =  os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        print " ->  MoabJobController: invoke %s" % cmd
        time.sleep(2)

        # print this after msub is run
        print "<JobID> " + "123456"
        print "<npes> " + "32"
        print "<nodes> " + "ml101 ml102"


        print "  LOTS of job data here ..."
    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    mjc = MoabJobController()

    sys.exit()
    
