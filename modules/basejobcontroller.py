#!python
"""  Base class to provide a template for all
     subsequent implementations of job launchers to
     follow (i.e. - Moab, slurm, ...)
 """

import sys,os
import subprocess
import time
import datetime


class BaseJobController():

    """ class to define the common actions for any job type """

    
    def __init__(self, name, configs, job_log_file):

        self.name = name
        self.configs = configs
        self.job_log_file = job_log_file

        self.save_common_settings()

        # move binaries and necessary files to temp working space
        self.setup_temp_working_space()

    def now(self):
        return datetime.datetime.now().strftime("%m-%d-%YT%H:%M%:%S")

    def setup_temp_working_space(self):


        ws_path = self.configs['working_space']['path']
        src_dir = self.configs['source_location']
        run_cmd = self.configs['run']['cmd'].split(".", 1)[0]


        # test specific working space takes first precedence

        ws=""
        try:
            if ws_path:
            # tack onto source location if relative
                if '.' in ws_path:
                    print "debug with ."
                    ws = src_dir + "/" + ws_path

            # how about noop option here!

            # else new full path as defined
                else:
                    print "debug full path"
                    ws = ws_path

        # if not specified for test make it just goes under the source location
            else:
                print "debug default path"
                ws = src_dir + "/pv_ws"

        except e:
            print "Error, coding bug if I get here!:w"


        # now setup and do the move
        os.environ['PV_WS'] = ws

        os.environ['PV_RUNHOME'] = ws + "/" + self.name + "__" + run_cmd + "." + self.now()

        print os.environ['PV_RUNHOME']

        #logging.info(self.now() + self.__class__.__name__ + ': setup RUNHOME')

        logging.info(self.now() + self.__class__.__name__ + ': setup RUNHOME')

        try:
            os.makedirs(os.environ['PV_RUNHOME'], 0o775)
        except:
            print "Error, could not create: ", ws, sys.exc_info()[0]

        from_loc = src_dir + "/"
        to_loc = os.environ['PV_RUNHOME']

        print "from: ", from_loc
        print "to: ", to_loc

        # support specified files to copy here!


        # build command for rsync
        cmd = "rsync -a --exclude 'pv_ws' --exclude '*.[ocfh]' --exclude '*.bck' --exclude '*.tar' "
        cmd += from_loc + " " + to_loc

        try:
            os.system(cmd)
        except:
            print "Error: rsync of src dir to ws failed!"




    def __str__(self):
        return 'instantiated %s object' % self.name

    # return the full path to where the logfile is located
    def get_results_directory(self):
        return os.path.dirname(self.job_log_file)


    # Invoke the correct way of running the job/test as defined in the
    # tests config entry.
    def start(self):
        pass

    # Print all the pertinent run data to the the job log file for later analysis.
    # Most of the <xxxx> stuff is for Gazebo backward compatibility
    def save_common_settings(self):

        obj_name = self.__class__.__name__
        print "#\n#  --- job: ", self.name, "-------"
        print "<rmgr> " + self.configs['run']['scheduler']
        print "<nix_pid> " + str(os.getpid())
        print "<testName> " + self.name
        print "<testExec> " + self.configs['run']['cmd']
        print "<user> " + os.getenv('USER')

        print self.configs

    def log(self):
        print

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

    sys.exit()
    
