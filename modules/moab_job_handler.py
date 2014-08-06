#!/usr/bin/env python

"""
# function similar to setUpandRun in Gazebo
# Perform necessary tasks associated with running the job
# after the msub allocation.
"""

import sys,os
import re


def find_jobid(message):
    '''Finds the jobid in the output from nmsub. The job id can either
    be just a number or Moab.number.'''
    # Optional \r because Windows python2.4 can't figure out \r\n is newline
    match=re.search("^((Moab.)?(\d+))[\r]?$",message,re.IGNORECASE|re.MULTILINE)
    if match:
        return match.group(1)
    return None

def find_moab_node_list():
    return "mu123 mu456"


def main():

    # all stdout and stderr set to write to log file in results directory

    # dummy line until on real Moab system
    jobid = 3
    #jobid = find_jobid(output)
    print "<JobID> " + str(jobid)

    print "<nodes> " + find_moab_node_list()

    sys.stdout.flush()

    # call the command that runs the users test/job
    cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + os.environ['USER_CMD']
    os.system(cmd)
    #os.system(os.environ['USER_CMD'])


# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
