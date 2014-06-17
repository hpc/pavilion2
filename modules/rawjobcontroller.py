#!python
"""  Implementation raw Job Control mechanism  """

import sys,os
import subprocess
from basejobcontroller import BaseJobController


class RawJobController(BaseJobController):
    """ class to run a test using no scheduler or special launcher """


    def start(self):

        # build the exact command to run
        cmd =  os.environ['PV_RUNHOME'] + "/" + self.configs['run']['cmd']
        print " ->  RawJobController: invoke %s" % cmd

        # Get any buffered output into the output file now
        # so that the the order doesn't look all mucked up
        sys.stdout.flush()

        # Invoke the cmd and send the output to the file setup when
        # the object was instantiated

        #p = subprocess.call(cmd, shell=True)
        p = subprocess.Popen(cmd, stdout=self.job_log_file, stderr=self.job_log_file, shell=True)
        # wait for the subprocess to finish
        output, errors = p.communicate()

        if p.returncode or errors:
            print "Error: something went wrong!"
            print [p.returncode, errors, output]

    def cleanup(self):

        self.logger.info(self.name + ': start cleanup')

        # if it exists and is executable call it. Script should print
        # to STDOUT to get output into log file
        es = self.configs['results']['epilog_script']

        self.logger.info(self.name + ': start cleanup with: '+ es)
        try:
            subprocess.Popen(es, stdout=self.job_log_file, stderr=self.job_log_file, shell=True)
        except:
           self.logger.error('Error, call to %s failed' % es)

        # clean up working space
        self.logger.info('remove WS: ' + os.environ['PV_RUNHOME'])
    
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    rjc = RawJobController()

    sys.exit()
    
