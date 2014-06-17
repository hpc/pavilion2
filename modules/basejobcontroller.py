#!python
"""  Base class to provide a template for all
     subsequent implementations of job launchers to
     follow (i.e. - Moab, slurm, ...)
 """

import sys,os
import subprocess
import time
import datetime
import logging


class BaseJobController():

    """ class to define the common actions for any job type """


    def __init__(self, name, configs, job_log_file):

        self.name = name
        self.configs = configs
        self.job_log_file = job_log_file

        self.logger = logging.getLogger('runjob.' + self.__class__.__name__)

        self.save_common_settings()

        # move binaries and necessary files to temp working space
        self.setup_temp_working_space()

    def now(self):
        return datetime.datetime.now().strftime("%m-%d-%YT%H:%M%:%S")

    def setup_temp_working_space(self):


        ws_path = self.configs['working_space']['path']
        src_dir = self.configs['source_location']
        run_cmd = self.configs['run']['cmd'].split(".", 1)[0]

        if 'NO-WS' in ws_path:
            os.environ['PV_WS'] = src_dir
            os.environ['PV_RUNHOME'] = src_dir
            print os.environ['PV_RUNHOME']
            print 'Working Space: %s' % os.environ['PV_RUNHOME']
            self.logger.info('WS for %s: ' % self.name + os.environ['PV_RUNHOME'])
            return

        # Otherwise ...
        # test specific working space takes first precedence

        if ws_path:
            # tack onto users home dir location if relative path provided
            if '.' in ws_path:
                print "debug with ."
                ws = os.environ['HOME'] + "/" + ws_path

            # else new full path as defined
            else:
                print "debug full path"
                ws = ws_path

        # not specified, so place it just under the source location
        else:
            print "debug default path"
            ws = src_dir + "/pv_ws"

        # now setup and do the move
        os.environ['PV_WS'] = ws
        os.environ['PV_RUNHOME'] = ws + "/" + self.name + "__" + run_cmd + "." + self.now()

        print 'Working Space: %s' % os.environ['PV_RUNHOME']

        self.logger.info('WS for ' + self.name + ":" + os.environ['PV_RUNHOME'])

        try:
            os.makedirs(os.environ['PV_RUNHOME'], 0o775)
        except:
            print "Error, could not create: ", ws, sys.exc_info()[0]

        from_loc = src_dir + "/"
        to_loc = os.environ['PV_RUNHOME']

        self.logger.debug('rsync source: %s' % from_loc)
        self.logger.debug('rsync dest: %s' % to_loc)

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

    def build(self):
        pass

    def kill(self):
        pass

    def query(self):
        pass

    def cleanup(self):
        """
            invoke the job specific routine that determines if job failed or passed.
        """
        pass 
        
        
        
# this gets called if it's run as a script/program
if __name__ == '__main__':

    sys.exit()
    
