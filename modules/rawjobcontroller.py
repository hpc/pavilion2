#!python
"""  Implementation raw Job Control mechanism  """

import sys,os
import subprocess
from basejobcontroller import BaseJobController

class RawJobController(BaseJobController):
    """ class to run a test using no scheduler or special launcher """

    # Invoke the correct way of running the job/test as defined in the
    # tests config entry.
    def start(self):

        cmd =  self.configs['location'] + "/" + self.configs['run']['cmd']
        print " ->  RawJobController: invoke %s" % cmd
        #subprocess.call([cmd])
        os.system(cmd)

    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    rjc = RawJobController()

    sys.exit()
    
