#!/usr/bin/env python

"""
# function similar to setUpandRun in Gazebo
# Perform necessary tasks associated with running the job
# after the msub allocation.
"""

import sys,os
from subprocess import Popen, PIPE
import subprocess
import shutil
import platform
import datetime

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
    if ("SLURM_JOBID" in os.environ):
        jid = os.environ.get("SLURM_JOBID")
        os.environ['RMGR'] = 'SLURM'
    if ("PBS_JOBID" in os.environ):
        jid = os.environ.get("PBS_JOBID")
        os.environ['RMGR'] = 'CLE'
    if (jid):
        os.environ['PV_JOBID'] = jid
        output = subprocess.check_output("../scripts/getNodeList", shell=True)
        nodes = output.replace('\n', " ")
        return str(nodes)
    else:
        return platform.node()

def run_epilog():

        es = os.environ['PV_ES']
        if es:
        # run an epilog script if defined in the test config
            print "starting epilog script" + str(es)
            os.system(es)
            print "epilog script complete"

def run_cleanup():

        print "start cleanup:"

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


    #cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + "ls -l"

    cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + os.environ['USER_CMD']
    nodes = get_moab_node_list()
    job_log_file = os.environ["PV_JOB_RESULTS_LOG"]

    with open(job_log_file, 'a') as lf:
        with stdout_redirected(lf):

            #redirect STDERR to the same file
            sys.stderr = lf

            print "<nodes> " + nodes + "\n"
            print "\n ->  moab_job_hander: invoke %s" % cmd
            lf.flush()

        # call the command that runs the users test/job

        # all these work with job_out_file = /users/cwi/mystdout
        #subprocess.call(cmd1, stdout=job_out_file, shell=True)
        #subprocess.call(cmd2, stdout=job_out_file, shell=True)
        #subprocess.call(cmd3, stdout=job_out_file, shell=True)

            #subprocess.call(cmd1, stdout=job_out_file, shell=True)
            subprocess.call(cmd, stdout=lf, stderr=lf, shell=True)

            run_epilog()

            if os.environ['PV_WS']:
                run_cleanup()

            print "<end>" , now()



# this gets called if it's run as a script/program
if __name__ == '__main__':
    sys.exit(main())
