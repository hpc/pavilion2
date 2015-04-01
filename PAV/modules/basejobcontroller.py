#!python

#  ###################################################################
#
#  Disclaimer and Notice of Copyright 
#  ==================================
#
#  Copyright (c) 2015, Los Alamos National Security, LLC
#  All rights reserved.
#
#  Copyright 2015. Los Alamos National Security, LLC. 
#  This software was produced under U.S. Government contract 
#  DE-AC52-06NA25396 for Los Alamos National Laboratory (LANL), 
#  which is operated by Los Alamos National Security, LLC for 
#  the U.S. Department of Energy. The U.S. Government has rights 
#  to use, reproduce, and distribute this software.  NEITHER 
#  THE GOVERNMENT NOR LOS ALAMOS NATIONAL SECURITY, LLC MAKES 
#  ANY WARRANTY, EXPRESS OR IMPLIED, OR ASSUMES ANY LIABILITY 
#  FOR THE USE OF THIS SOFTWARE.  If software is modified to 
#  produce derivative works, such modified software should be 
#  clearly marked, so as not to confuse it with the version 
#  available from LANL.
#
#  Additionally, redistribution and use in source and binary 
#  forms, with or without modification, are permitted provided 
#  that the following conditions are met:
#  -  Redistributions of source code must retain the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer. 
#  -  Redistributions in binary form must reproduce the 
#     above copyright notice, this list of conditions 
#     and the following disclaimer in the documentation 
#     and/or other materials provided with the distribution. 
#  -  Neither the name of Los Alamos National Security, LLC, 
#     Los Alamos National Laboratory, LANL, the U.S. Government, 
#     nor the names of its contributors may be used to endorse 
#     or promote products derived from this software without 
#     specific prior written permission.
#   
#  THIS SOFTWARE IS PROVIDED BY LOS ALAMOS NATIONAL SECURITY, LLC 
#  AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, 
#  INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF 
#  MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. 
#  IN NO EVENT SHALL LOS ALAMOS NATIONAL SECURITY, LLC OR CONTRIBUTORS 
#  BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, 
#  OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, 
#  PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, 
#  OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY 
#  THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR 
#  TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT 
#  OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY 
#  OF SUCH DAMAGE.
#
#  ###################################################################


"""  Base class to provide a template for all
     subsequent implementations of job launchers to
     follow (i.e. - Moab, slurm, ...)
 """

import sys
import os
import re
import datetime
import logging
import shutil
import json
import glob
from subprocess import Popen, PIPE


def copy_file(src, dest):
    try:
        shutil.copy(src, dest)
    # eg. src and dest are the same file
    except shutil.Error as e:
        print('Error: %s' % e)
    # eg. source or destination doesn't exist
    except IOError as e:
        print('Error: %s' % e.strerror)


class JobController():

    """ class to define the common actions for any job type """

    @staticmethod
    def now():
        return datetime.datetime.now().strftime("%m-%d-%YT%H:%M:%S:%f")

    def __init__(self, uid, configs, job_log_file, job_variation):

        self.uid = uid
        self.name = configs['name']
        self.configs = configs
        self.job_log_file = job_log_file
        self.job_variation = job_variation
        self.lh = self.configs['log_handle']

        # setup logging same as in pav
        self.logger = logging.getLogger('pav.' + self.__class__.__name__)
        self.logger.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        master_log_file = os.environ['PV_LOG']
        fh = logging.FileHandler(filename=master_log_file)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        #print "initialize job controller"

        # verify command is executable early on
        mycmd = self.configs['source_location'] + "/" + self.configs['run']['cmd']
        is_exec = os.access(mycmd, os.X_OK)
        if not is_exec:
            print mycmd + " Run command not executable!"
            self.logger.error('%s %s not executable' % (self.lh + ":", mycmd))
            raise RuntimeError('Run command not executable')

        self.logger.info(self.lh + " : init phase")

        # Define commonly used  global env variables for this job/test.
        # GZ_ vars for backwards compatibility with Gazebo, but to be
        # removed sometime down the road.

        os.environ['PV_TESTNAME'] = self.name
        os.environ['GZ_TESTNAME'] = self.name
        os.environ['PV_TESTEXEC'] = self.configs['run']['cmd']
        os.environ['GZ_TESTEXEC'] = self.configs['run']['cmd']
        pt = type(self.configs['run']['test_args'])
        try:
            os.environ['GZ_TEST_PARAMS'] = self.configs['run']['test_args']
            os.environ['PV_TEST_ARGS'] = self.configs['run']['test_args']
            #os.environ['PV_TEST_ARGS'] = "is a string"
            #os.environ['GZ_TEST_PARAMS'] = "is a string"

        except:
            raise TypeError('test_args value problem, is it a string?')

        self.setup_working_space()

    def setup_working_space(self):

        ws_path = self.configs['working_space']['path']
        src_dir = self.configs['source_location']
        run_cmd = self.configs['run']['cmd'].split(".")[0]

        exclude_ws = ''
        if ws_path:
            # it's either a relative path to the src directory
            # or it's an absolute one.
            if '/' in ws_path[0]:
                ws = ws_path
            else:
                ws = src_dir + "/" + ws_path
                exclude_ws = ws_path

        # Working space is null, thus directed to run directly from the source directory
        # so no further work necessary.
        else:
            os.environ['PV_WS'] = ""
            os.environ['PV_RUNHOME'] = src_dir
            print os.environ['PV_RUNHOME']
            print 'Working Space: %s' % os.environ['PV_RUNHOME']
            self.logger.info('Working Space for %s: ' % self.lh + os.environ['PV_RUNHOME'])
            return

        # now setup and do the move
        os.environ['PV_RUNHOME'] = ws + "/" + self.name + "__" + run_cmd + "." + JobController.now()

        print 'Working Space: %s' % os.environ['PV_RUNHOME']

        self.logger.info(self.lh + " : " + 'Create temporary Working Space - ' + os.environ['PV_RUNHOME'])
        try:
            os.makedirs(os.environ['PV_RUNHOME'], 0o775)
        except OSError:
            print "Error, could not create: ", ws, sys.exc_info()[0]
            #self.logger.error(self.lh + " Error, Failed to create working space (WS)")
            raise RuntimeError("Can't create temporary work space (WS)")

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
                cmd = "rsync -a --exclude '" + \
                      exclude_ws + "' --exclude '*.[ocfh]' --exclude '*.bck' --exclude '*.tar' "
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
            self.logger.info(self.lh + " failed copying data to working space!, skipping job: " + self.name +
                                       "(Hint: check the job logfile)")

    def __str__(self):
        return 'instantiated %s object' % self.name

    # return the full path to where the logfile is located
    def get_results_directory(self):
        return os.path.dirname(self.job_log_file)

    # Print all the pertinent run data to the the job log file for later analysis.
    # Most of the <xxxx> stuff is for Gazebo backward compatibility
    def save_common_settings(self):

        print "#\n#  --- job: ", self.name, "-------"
        print "<rmgr> " + self.configs['run']['scheduler']
        print "<nix_pid> " + str(os.getpid())
        print "<testName> " + self.name
        print "<testExec> " + self.configs['run']['cmd']
        print "<user> " + os.getenv('USER')
        print "<params> " + os.environ['PV_TEST_ARGS']
        #print "<segName> " + "theTargetSeg"
        sys.stdout.flush()

        # save the test config
        tcf = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/test_config.txt"
        tcf_file = open(tcf, "w+")
        tcf_file.write("Pavilion configuration values used to run this test:\n\n")
        tcf_file.write(json.dumps(self.configs, sort_keys=True, indent=4))
        tcf_file.close()

    def build(self):
        # call the command that builds the users test/job
        bld_cmd = self.configs['source_location'] + "/" + self.configs['build']['cmd']
        self.logger.info(self.lh + ': start build command: ' + bld_cmd)
        os.system(bld_cmd)
        self.logger.info(self.lh + '%s build command complete ' % bld_cmd)

    def query(self):
        pass

    @staticmethod
    def run_epilog():
        # run an epilog script if defined in the test config

        try:
            if os.environ['PV_ES']:
            # run an epilog script if defined in the test config
                es = os.environ['PV_ES']
                print "- Run epilog script: " + str(es)
                os.system(es)
                print "- epilog script complete"
        except KeyError, e:
                #print 'I got a KeyError - no: "%s"' % str(e)
                print "- No epilog script configured"
                pass

    def setup_job_info(self):

        # save for later reference
        os.environ['PV_SAVE_FROM_WS'] = self.configs['working_space']['save_from_ws']

        os.environ['PV_ES'] = self.configs['results']['epilog_script']

        os.environ['GZ_RUNHOME'] = os.environ['PV_RUNHOME']

        os.environ['GZ_LOGFILE'] = os.environ["PV_JOB_RESULTS_LOG"]

        os.environ['PV_TEST_ARGS'] = self.configs['run']['test_args']
        os.environ['GZ_TEST_PARAMS'] = os.environ['PV_TEST_ARGS']

        #os.environ['TD_REGX'] = self.configs['results']['trend_data_regex']

        try:
            if self.configs['splunk']['state']:
                os.environ['SPLUNK_DATA_LOG'] = str(self.configs['splunk']['global_data_file'])
        except KeyError, e:
            print 'basejobcontroller:setup_job_info, Splunk config error - no: "%s"' % str(e)
            pass


    @staticmethod
    def cleanup():

        print '- Start WS cleanup:'

        sys.stdout.flush()
        sys.stderr.flush()

        # Save the files from the RUNHOME, a.k.a. WS directory
        from_loc = os.environ['PV_RUNHOME'] + "/"
        to_loc = os.environ["PV_JOB_RESULTS_LOG_DIR"]

        #print '  files in :' + from_loc
        #print '  copy to  :' + to_loc

        # save explicitly defined files in the test suite config file
        try:
            if os.environ['PV_SAVE_FROM_WS']:
                no_spaces_str = "".join(os.environ['PV_SAVE_FROM_WS'].split())
                for file_type in no_spaces_str.split(","):
                    print "  save files like: " + file_type
                    for file2save in glob.glob(os.path.join(from_loc, file_type)):
                        print "  saving: " + file2save
                        copy_file(file2save, to_loc)
        except KeyError, e:
            #print 'I got a KeyError - no: "%s"' % str(e)
            pass

        # remove the working space ONLY if it was created
        try:
            if os.environ['PV_WS']:
                print '- remove WS: %s ' % os.environ['PV_RUNHOME']
                shutil.rmtree(os.environ['PV_RUNHOME'])
        except KeyError, e:
            #print 'I got a KeyError - no: "%s"' % str(e)
            pass

        print '- WS cleanup complete'

    @staticmethod
    def process_trend_data():

        # slurp up the trend data from the log file and place it in a file
        # called trend_data in the results dir
        tdf = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/trend_data"
        out_file = open(tdf, "w")

        lf = open(os.environ["PV_JOB_RESULTS_LOG"], 'r')

        for line in lf:
            #td_regex = os.environ['TD_REGX']
            #match = re.search(td_regex, line, re.IGNORECASE)
            match = re.search("^(<td>\s+(.*))", line, re.IGNORECASE)
            if match:
                out_file.write(match.group(2) + "\n")

        out_file.close()

        # generate Splunk data file(s) (if configured on in test suite file)
        try:
            if os.environ['SPLUNK_DATA_LOG']:
                log_dir = os.environ['PV_JOB_RESULTS_LOG_DIR']
                cmd = os.environ['PVINSTALL'] + "/PAV/scripts/splunk/td2splunkData " + log_dir
                os.system(cmd)
        except KeyError, e:
            # Never set up properly so just move on...
            #print 'basejobcontroller:process_trend_data, KeyError - no: "%s"' % str(e)
            pass


# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit()
