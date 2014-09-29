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

newpath = os.environ['PV_SRC_DIR'] + "/modules"
sys.path.append(newpath)
from basejobcontroller import BaseJobController
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
        output = subprocess.check_output("./scripts/getNodeList", shell=True)
        nodes = output.replace('\n', " ")
        return str(nodes)
    else:
        return platform.node()


def run_epilog():

        if os.environ['PV_ES']:
        # run an epilog script if defined in the test config
            es = os.environ['PV_ES']
            print "starting epilog script" + str(es)
            os.system(es)
            print "epilog script complete"


def run_cleanup():

        print "start cleanup:"

        # Save the necessary files from the RUNHOME directory
        from_loc = os.environ['PV_RUNHOME'] + "/"
        to_loc = os.environ["PV_JOB_RESULTS_LOG_DIR"]

        files2copy = ''
        if os.environ['PV_SAVE_FROM_WS']:
            files2copy = " --include " + os.environ['PV_SAVE_FROM_WS']

        # add the basics
        files2copy += " --include '*.log' --include '*.stderr' --include '*.stdout' --exclude='*' "

        # finalize complete command
        cmd = "rsync -ar " + files2copy + " " + from_loc + " " + to_loc

        print "cmd -> " + cmd

        # do it
        p = Popen(cmd, stdout=PIPE, stderr=PIPE, shell=True)
        output, errors = p.communicate()

        if p.returncode or errors:
            print [p.returncode, errors, output]
            print "Failure copying job results to the output directory:  (Hint: check the job's logfile) "

        # remove the working space only if it was created
        if os.environ['PV_WS']:
            #print "Remove WS - %s " % os.environ['PV_RUNHOME']
            shutil.rmtree(os.environ['PV_RUNHOME'])


def main():

    #cmd1 = "cd " + os.environ['PV_RUNHOME'] + "; " + "ls -l"
    cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + \
        os.environ['PV_SRC_DIR'] + "/scripts/mytime " + os.environ['USER_CMD']

    nodes = get_moab_node_list()
    job_log_file = os.environ["PV_JOB_RESULTS_LOG"]

    with open(job_log_file, 'a') as lf:
        with stdout_redirected(lf):

            #redirect STDERR to the same file
            sys.stderr = lf

            print "<nodes> " + nodes + "\n"
            print "moab_job_handler: "

            # start LDMS here if requested!  If the start command is
            # defined, then it's a go!
            if os.environ['LDMS_START_CMD']:
                print "  start ldms with: \n    " + os.environ['LDMS_START_CMD']
                LDMS.start(os.environ['LDMS_START_CMD'])

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
            run_epilog()
            text_file.write("{}\n".format("epilog complete"))
            run_cleanup()
            text_file.write("{}\n".format("cleanup complete"))
            text_file.close()

            print "<end>", now()

            # The trend_data file needs to be placed in the results dir
            # for Gazebo compatibility
            BaseJobController.process_trend_data()


# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
