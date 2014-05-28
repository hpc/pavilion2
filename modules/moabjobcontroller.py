#!python
"""  Implementation of Moab Job Controller  """

import sys
import subprocess
from basejobcontroller import BaseJobController

class MoabJobController(BaseJobController):
    """ class to run/stop a job using Moab """

    # Invoke the correct way of running the job/test as defined in the
    # tests config entry.
    def start(self):

        cmd =  self.configs['location'] + "/" + self.configs['run']['cmd']
        print " ->  MoabJobController: invoke %s" % cmd
    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    mjc = MoabJobController()

    sys.exit()
    
