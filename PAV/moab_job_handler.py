#!/usr/bin/env python

"""
# function similar to setUpandRun in Gazebo
# Perform necessary tasks associated with running the job
# after the msub allocation.
"""

import sys,os


from contextlib import contextmanager


def main():

    # setup so that all stdout and stderr goes to log file in the working space(RUNHOME)

    # call the command that runs the users test/job
    os.system(os.environ['USER_CMD'])

    # CLEANUP all the junk in RUNHOME
    # and remove the working space if PV_WS was set,
    # otherwise the job was running out of the actual test dir.
    from_loc = os.environ['PV_RUNHOME'] + "/"
    to_loc = os.environ["PV_JOB_RESULTS_LOG_DIR"]
    if (os.environ['PV_WS']):
        # copy all the contents in this case
        cmd_cp = "rsync -a  " + from_loc + " " + to_loc
        cmd_rm = "rm -rf " + os.environ['PV_WS']
        os.system(cmd_rm)
    else:
                # just a few select files in this case
        cmd_cp = "rsync -a --include '*.log' --include '*.stderr'--include '*.stdout' "
        cmd_cp += from_loc + " " + to_loc



# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
