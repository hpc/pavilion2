#!python
"""  Base class to provide a template for all
     subsequent implementations of job launchers to
     follow (i.e. - Moab, slurm, ...)
 """

import sys,os
import datetime
import logging
import shutil
from subprocess import Popen, PIPE


class BaseJobController():

    """ class to define the common actions for any job type """

    def now(self):
        return datetime.datetime.now().strftime("%m-%d-%YT%H:%M:%S:%f")


    def __init__(self, name, configs, job_log_file, job_variation):

        self.name = name
        self.configs = configs
        self.job_log_file = job_log_file
        self.job_variation = job_variation
        self.lh = self.configs['log_handle']

        self.logger = logging.getLogger('pth.runjob.' + self.__class__.__name__)

        # verify command is executable early on
        mycmd = self.configs['source_location'] + "/" + self.configs['run']['cmd']
        is_exec = os.access(mycmd, os.X_OK)
        if not is_exec:
            print self.configs['run']['cmd'] + " command not executable, returning!"
            self.logger.error('%s %s not executable, returning!' % (self.lh + ":", mycmd))
            raise RuntimeError('some error message')

        self.logger.info(self.lh + " : init phase ")
        #self.save_common_settings()

        # common global env params for this job
        os.environ['PV_TESTNAME'] = self.name
        os.environ['GZ_TESTNAME'] = self.name
        os.environ['PV_TESTEXEC'] = self.configs['run']['cmd']
        os.environ['GZ_TESTEXEC'] = self.configs['run']['cmd']
        os.environ['GZ_TEST_PARAMS'] = self.configs['run']['test_args']
        os.environ['PV_TEST_ARGS'] = self.configs['run']['test_args']



    def setup_working_space(self):


        ws_path = self.configs['working_space']['path']
        src_dir = self.configs['source_location']
        run_cmd = self.configs['run']['cmd'].split(".")[0]

        exclude_ws = ''
        if ws_path:
            # it's either a relative path from the src directory
            # or it's an absolute one.
            if '/' in ws_path[0]:
                ws = ws_path
            else:
                ws = src_dir + "/" + ws_path
                exclude_ws = ws_path


        # working space is null, so run source directory
        else:
            os.environ['PV_WS'] = ""
            os.environ['PV_RUNHOME'] = src_dir
            print os.environ['PV_RUNHOME']
            print 'Working Space: %s' % os.environ['PV_RUNHOME']
            self.logger.info('WS for %s: ' % self.lh + os.environ['PV_RUNHOME'])
            return


        # now setup and do the move

        os.environ['PV_RUNHOME'] = ws + "/" + self.name + "__" + run_cmd + "." + self.now()

        print 'Working Space: %s' % os.environ['PV_RUNHOME']

        self.logger.info(self.lh + " : " + 'Create WS - ' + os.environ['PV_RUNHOME'])

        try:
            os.makedirs(os.environ['PV_RUNHOME'], 0o775)
        except:
            print "Error, could not create: ", ws, sys.exc_info()[0]

        to_loc = os.environ['PV_RUNHOME']
        os.environ['PV_WS'] = to_loc


        # support user specified files or dirs to copy here.
        files2copy = self.configs['working_space']['copy_to_ws']
        if files2copy:
            cmd = "cd " + src_dir + "; rsync -ar " + files2copy + " " + to_loc
        # general case is to copy all files except some known source file types
        else:
            from_loc = src_dir + "/"
            if exclude_ws:
                cmd = "rsync -a --exclude '" + exclude_ws  + "' --exclude '*.[ocfh]' --exclude '*.bck' --exclude '*.tar' "
            else:
                cmd = "rsync -a --exclude '*.[ocfh]' --exclude '*.bck' --exclude '*.tar' "
            cmd += from_loc + " " + to_loc


        self.logger.debug('%s : %s' % (self.lh, cmd))

        # run the command
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        output, errors = p.communicate()

        if p.returncode or errors:
            print "Error: failed copying data to working space!"
            print [p.returncode, errors, output]
            self.logger.info(self.lh + " failed copying data to working space!, skipping job: " + self.name +\
                " (Hint: check the job logfile) ")



    def __str__(self):
        return 'instantiated %s object' % self.name

    # return the full path to where the logfile is located
    def get_results_directory(self):
        return os.path.dirname(self.job_log_file)


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

        sys.stdout.flush()

    def build(self):
        # call the command that builds the users test/job
        bld_cmd = self.configs['source_location'] + "/" + self.configs['build']['cmd']
        self.logger.info(self.lh + ': start build command: '+ bld_cmd)
        os.system(bld_cmd)
        self.logger.info(self.lh + '%s build command complete ' % bld_cmd)

    def query(self):
        pass

    def run_epilog(self):
        es = self.configs['results']['epilog_script']

        # run an epilog script if defined in the test config
        if es:
            self.logger.info(self.lh + ': start epilog script: '+ es)
            os.system(es)
            self.logger.info(self.lh + '%s epilog script complete' % es)

    def setup_job_info(self):

        # save for later reference
        os.environ['PV_SAVE_FROM_WS'] = self.configs['working_space']['save_from_ws']

        os.environ['PV_ES'] = self.configs['results']['epilog_script']

        os.environ['GZ_RUNHOME'] = os.environ['PV_RUNHOME']

        os.environ['GZ_LOG_FILE'] = os.environ["PV_JOB_RESULTS_LOG"]


    def cleanup(self):

        self.logger.info(self.lh + ': start cleanup')

        sys.stdout.flush()
        sys.stderr.flush()

        # Save the necessary files from the RUNHOME directory
        from_loc = os.environ['PV_RUNHOME'] + "/"
        to_loc = os.environ["PV_JOB_RESULTS_LOG_DIR"]

        files2copy = ''
        #if (self.configs['working_space']['save_from_ws']):
        if os.environ['PV_SAVE_FROM_WS']:
            files2copy = " --include " + os.environ['PV_SAVE_FROM_WS']

        # add the basics
        files2copy += " --include '*.log' --include '*.stderr' --include '*.stdout' --exclude='*' "

        # finalize complete command
        cmd = "rsync -ar " + files2copy + " " + from_loc + " " + to_loc

        self.logger.debug('%s : %s' % (self.lh, cmd))

        # do it
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        output, errors = p.communicate()

        if p.returncode or errors:
            print "Error: failure copying job results the output directory!"
            print [p.returncode, errors, output]
            self.logger.info(self.lh + " failure copying job results to the output directory: " + self.name +\
                " (Hint: check the job's logfile) ")


        # remove the working space if it was created
        #if self.configs['working_space']['path']:
        if os.environ['PV_WS']:
            self.logger.info('%s : remove WS - %s ' % (self.lh, os.environ['PV_RUNHOME']))
            shutil.rmtree(os.environ['PV_RUNHOME'])

        
# this gets called if it's run as a script/program
if __name__ == '__main__':

    sys.exit()
    
