#!/usr/bin/env python

"""
# function similar to setUpandRun in Gazebo
# Perform necessary tasks associated with running the job
# after the msub allocation.
"""

import sys,os


from contextlib import contextmanager
@contextmanager
def stdout_redirected(new_stdout):
    save_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield None
    finally:
        sys.stdout = save_stdout

def collect_moab_node_list():
    return "mu123 mu456"

def get_moab_job_id():
    return "123456"

def main():

    # setup so all stdout and stderr goes to log file in the working space(RUNHOME)
    jobid = get_moab_job_id()
    joblog = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/" + jobid + ".log"

    with open(joblog, "w+") as jlf:
        with stdout_redirected(jlf):

            #redirect STDERR to the same file
            sys.stderr = jlf

            print "<JobID> " + jobid
            print "<nnodes> " + os.environ['PV_NNODES']
            print "<nodes> " + collect_moab_node_list()
            print "<npes> " + os.environ['PV_NPES']

            # call the user command
            os.system(os.environ['USER_CMD'])

            # wait for drm er/ou files to show up
            # probably limit this wait to a min or 2...

            # copy all the junk in RUNHOME to the final results dir
            # and
            # remove the working space, only if PV_WS is set,
            # otherwise the job was running out of the real test home.
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
