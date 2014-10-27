#!/usr/bin/env python

"""
# Functions similar to setUpandRun in Gazebo.
# Application that is called by msub.
"""

import sys
import os
from subprocess import Popen, PIPE
import subprocess
import shutil
import platform
import datetime

newpath = os.environ['PVINSTALL'] + "/PAV/modules"
sys.path.append(newpath)
from basejobcontroller import JobController
from ldms import LDMS


def now():
    return " " + datetime.datetime.now().strftime("%m-%d-%YT%H:%M:%S")

from contextlib import contextmanager
@contextmanager
def stdout_redirected(new_stdout):
    save_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield None
    finally:
        sys.stdout = save_stdout


def get_moab_node_list():

    os.environ['RMGR'] = ''
    jid = ''
    if "SLURM_JOBID" in os.environ:
        jid = os.environ.get("SLURM_JOBID")
        os.environ['RMGR'] = 'SLURM'
    if "PBS_JOBID" in os.environ:
        jid = os.environ.get("PBS_JOBID")
        os.environ['RMGR'] = 'CLE'
    if jid:
        os.environ['PV_JOBID'] = jid
        output = subprocess.check_output(os.environ['PVINSTALL'] + "/PAV/scripts/getNodeList", shell=True)
        nodes = output.replace('\n', " ")
        return str(nodes)
    else:
        return platform.node()


def main():
    """
      Routine called by msub that calls the user's job script/program.
      Will also start LDMS if requested.
    """
    cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + \
        os.environ['PVINSTALL'] + "/PAV/scripts/mytime " + os.environ['USER_CMD']

    nodes = get_moab_node_list()
    os.environ['PV_NODES'] = nodes
    os.environ['GZ_NODES'] = os.environ['PV_NODES']
    job_log_file = os.environ["PV_JOB_RESULTS_LOG"]

    with open(job_log_file, 'a') as lf:
        with stdout_redirected(lf):

            #redirect STDERR to the same file
            sys.stderr = lf

            print "<nodes> " + nodes + "\n"
            print "moab_job_handler: "

            # start LDMS here if requested!  The start command ought to be
            # defined, so let's go!
            if os.environ['LDMS_START_CMD']:
                LDMS.start()

            print "  start job with: \n    " + cmd
            lf.flush()

            # Call the command that runs the users test/job
            # This works with job_out_file = /users/cwi/mystdout
            #subprocess.call(cmd1, stdout=job_out_file, shell=True)

            subprocess.call(cmd, stdout=lf, stderr=lf, shell=True)

            # The post_complete file needs to be placed in the results dir
            # for Gazebo compatibility
            pcf = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/post_complete"
            text_file = open(pcf, "w")
            text_file.write("{}\n".format("command complete"))
            JobController.run_epilog()
            text_file.write("{}\n".format("epilog complete"))
            JobController.cleanup()
            text_file.write("{}\n".format("cleanup complete"))
            text_file.close()

            print "<end>", now()

            # The trend_data file needs to be placed in the results dir
            # for Gazebo compatibility
            JobController.process_trend_data()


# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
