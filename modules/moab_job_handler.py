#!/usr/bin/env python

"""
# function similar to setUpandRun in Gazebo
# Perform necessary tasks associated with running the job
# after the msub allocation.
"""

import sys,os
import re
from subprocess import Popen, PIPE
import subprocess
import shutil



def find_jobid(message):
    '''Finds the jobid in the output from msub. The job id can either
    be just a number or Moab.number.'''
    # Optional \r because Windows python2.4 can't figure out \r\n is newline
    match=re.search("^((Moab.)?(\d+))[\r]?$",message,re.IGNORECASE|re.MULTILINE)
    if match:
        return match.group(1)
    return None

def find_moab_node_list():

    #if os.environ['PV_JOBID']:
    #    return "me123 mu456"
    #else:
    return "fake123 fake456"

def run_epilog():

        es = os.environ['PV_ES']
        if es:
        # run an epilog script if defined in the test config
            print "starting epilog script" + str(es)
            os.system(es)
            print "epilog script complete"

def run_moab_cleanup():

        print "start cleanup"

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

        print "cmd -> " +  cmd

        # do it
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        output, errors = p.communicate()

        if p.returncode or errors:
            print [p.returncode, errors, output]
            print "Failure copying job results to the output directory:  (Hint: check the job's logfile) "


        # remove the working space if it was created
        if os.environ['PV_WS']:
            print "Remove WS - %s " % os.environ['PV_RUNHOME']
            shutil.rmtree(os.environ['PV_RUNHOME'])



def main():

    #job_out_file = open(os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/stdout", "w+")
    #job_out_file.write(" STDOUT from: " + os.environ['USER_CMD'] + "\n")
    #job_out_file.flush()

    #cmd1 = "ls -l"
    #cmd2 = "cd " + os.environ['PV_RUNHOME'] + "; " + "ls -l"
    cmd3 = "cd " + os.environ['PV_RUNHOME'] + "; " + os.environ['USER_CMD']

    print "am I here?"
    job_log_file = os.environ["PV_JOB_RESULTS_LOG"]
    with open(job_log_file, 'a') as f:

        f.write("hello there")
        f.write("<nodes> " + find_moab_node_list() + "\n")
        f.write("bye")
        f.flush()

        # call the command that runs the users test/job

        # all these work with job_out_file = /users/cwi/mystdout
        #subprocess.call(cmd1, stdout=job_out_file, shell=True)
        #subprocess.call(cmd2, stdout=job_out_file, shell=True)
        #subprocess.call(cmd3, stdout=job_out_file, shell=True)

        #subprocess.call(cmd1, stdout=job_out_file, shell=True)
        subprocess.call(cmd3, stdout=f, shell=True)

        run_epilog()
        if os.environ['PV_WS']:
            run_moab_cleanup()



# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
