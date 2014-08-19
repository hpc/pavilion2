#!/usr/bin/env python

"""
# function similar to setUpandRun in Gazebo
# Perform necessary tasks associated with running the job
# after the msub allocation.
"""

import sys,os
import re
import subprocess



def find_jobid(message):
    '''Finds the jobid in the output from msub. The job id can either
    be just a number or Moab.number.'''
    # Optional \r because Windows python2.4 can't figure out \r\n is newline
    match=re.search("^((Moab.)?(\d+))[\r]?$",message,re.IGNORECASE|re.MULTILINE)
    if match:
        return match.group(1)
    return None

def find_moab_node_list():
    return "mu123 mu456"

def run_epilog():

        es = os.environ['PV_ES']
        if es:
        # run an epilog script if defined in the test config
            print "starting epilog script" + str(es)
            os.system(es)
            print "epilog script complete"

def run_cleanup():


    print "run cleanup script"
    if os.environ['PV_SAVE_FROM_WS']:
        print "save " + os.environ['PV_SAVE_FROM_WS'] + " files"


def main():

    #job_out_file = open(os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/stdout", "w+")
    #job_out_file.write(" STDOUT from: " + os.environ['USER_CMD'] + "\n")
    #job_out_file.flush()

    #cmd1 = "ls -l"
    #cmd2 = "cd " + os.environ['PV_RUNHOME'] + "; " + "ls -l"
    cmd3 = "cd " + os.environ['PV_RUNHOME'] + "; " + os.environ['USER_CMD']

    job_log_file = os.environ["PV_JOB_RESULTS_LOG"]
    with open(job_log_file, 'a') as f:

        f.write("<nodes> " + find_moab_node_list() + "\n")
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
            run_cleanup()



# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
