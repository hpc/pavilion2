#!python
"""  Base class to provide a template for all
     subsequent implementations of job launchers to
     follow (i.e. - Moab, slurn, ...)
 """

import sys,os
import subprocess
import time
import datetime

class BaseJobController():

    """ class to define the common actions for any job cycle """

    
    def __init__(self, name, configs, output_file):

        self.name = name
        self.configs = configs
        self.output_file = output_file

        """
          A common set of things happen for each job type...
          1) create final resuts directory and output log
          2) save start time and config setting to log file
          3) if necessary, create the working_space and move
             the proper files there
        """

        self.set_results_directory()

        self.save_common_settings()

    def __str__(self):
        return 'instantiated %s object' % self.name

    def get_results_directory(self):
        return self.res_dir

    def set_results_directory(self):

        # start by making placeholder for the results for any attempted job launch
        # Simple version now,  need to enhance like Gazebo result dir
        self.res_dir = self.configs['results']['root']
        self.res_dir = os.path.expanduser(self.res_dir)

        try:
            os.makedirs(self.res_dir, 0775)
        except OSError:
            pass



    # Invoke the correct way of running the job/test as defined in the
    # tests config entry.
    def start(self):
        pass

    # record all the pertinent run data to the log file for later analysis
    def save_common_settings(self):
        #print "\n\nsave what I know for job: %s" % self.name
        print "basejobcontroller: <job_type> %s" % self.configs['run']['scheduler']
        print "basejobcontroller: <nix_pid> %s" % str(os.getpid())
        print self.configs

    def build(self):
        pass

    def kill(self):
        pass

    def query(self):
        pass

    def cleanup(self):
        pass 
        
        
        
# this gets called if it's run as a script/program
if __name__ == '__main__':
    
    # instantiate a class to handle the config files
    gtr = GenTestRunner()

    sys.exit()
    
