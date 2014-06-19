#!/usr/bin/env python

""" this stand-alone program supports running jobs for any scheduler type
"""

import sys,os
import time
import datetime, pytz
import json
import logging
import errno
import platform
from signal import signal, SIGPIPE, SIG_DFL

# handle for all loggin
logger = ""

def convert(input):
    if isinstance(input, dict):
        return {convert(key): convert(value) for key, value in input.iteritems()}
    elif isinstance(input, list):
        return [convert(element) for element in input]
    elif isinstance(input, unicode):
        return input.encode('utf-8')
    else:
        return input

from contextlib import contextmanager
@contextmanager
def stdout_redirected(new_stdout):
    save_stdout = sys.stdout
    sys.stdout = new_stdout
    try:
        yield None
    finally:
        sys.stdout = save_stdout



# something to write to the log for now
def greet(greeting='hello'):
    print 'greetings earthling!' 
    print "er ...   "
    print greeting + " world!"

def load_jcmod(name, params):

    """
        Basically trying to dynamically load the correct job controller
        (perform a 'from typejobcontroller import TypeJobController')
    """

    # build with a known naming convention
    module_name = params['run']['scheduler'] + "jobcontroller"
    class_name_Cc = params['run']['scheduler'].title() + "JobController"

    sys.path.append("../modules")

    try:

        # dynamically import the desired module
        mh = __import__(module_name)

    except:
        print "Warning: no job controller for scheduler type %s"  % params['run']['scheduler']
        print "  Skipping job %s" % name
        return

    # get a reference to the JobController class
    class_ = getattr(mh, class_name_Cc)
    return class_

def build_results_dir(params, name):

    """ function to create the final result directory for a job/test.
        Intent is to make backwards compatible with Gazebo.
    """

    root_result_dir = params['results']['root']
    new_dir = root_result_dir + "/gzshared/"
    date_parts = datetime.datetime.now().strftime("%Y/%Y-%m/%Y-%m-%d/")
    target = platform.uname()[1].split(".", 1)[0]
    new_dir = new_dir +  date_parts + target + "/" + name + "/"
    pid = str(os.getpid())
    my_timezone = params['time']['tz']
    ld = name + "__" + params['run']['cmd'].split(".", 1)[0] + \
         "__" + pid + "__" + target  \
         + "." + datetime.datetime.now(pytz.timezone(my_timezone)).strftime('%Y-%m-%dT%H:%M:%S%z')
    new_dir += ld

    try:
        os.umask(0o002)
        os.makedirs(new_dir, 0o775)
    except OSError as e:
        if e.errno == errno.EEXIST:
            logger.info(new_dir + " exists")
            pass
        else:
            logger.info(new_dir + "something bad")
            raise

    return new_dir


def now():
    return " " + datetime.datetime.now().strftime("%m-%d-%YT%H:%M%:%S")

        
def main(args):

    """ performs the task of running the job defined by the args sent to this handler.
        There may be no terminal associated with this program so all output from the job
        is now directed to a corresponding log file. This program
        functions loosely like the setUpandRun wrapper script from Gazebo.
    """

    logger = logging.getLogger('pth.runjob')
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(filename='/tmp/pth.log')
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    params = json.loads(args[2])
    params = convert(params)
    name = args[1]


    #signal(SIGPIPE,SIG_DFL)


    # Load the correct JobController module for this specific job/test
    jc = load_jcmod(name, params)

    logger.info("Process- " + name)
    # all STDOUT and STDERR from job directed to its own log file
    logfile = build_results_dir(params, name) + "/" + name + ".log"
    logger.info(name + ": logfile -> %s" % logfile)

    os.environ["PV_JOB_RESULTS_LOG"] = logfile
    with open(logfile, "w+") as lf:
        with stdout_redirected(lf):
                
            #redirect STDERR to the same file
            sys.stderr = lf

            try:
            # instantiate job controller object
                this_job = jc(name, params, lf)
            except:
                print "Error: runjob: inst job object died, exiting job"
                logging.error(name + ' inst job object died, exiting job ')
                return

            # do what every job has to do
            logger.info(name + ' Starting ')
            if params['build']['build_before_run_flag']:
                logger.info(name + " build-start ")
                print "<build-start> ", now()
                this_job.build()
                logger.info(name + " build-end ")
                print "<build-end> ", now()
            print "<start> " , now()
            this_job.start()
            print "<end> " , now()
            this_job.cleanup()
            logger.info(name + ' Completed ')




# this gets called if it's run as a script from the shell
if __name__ == '__main__':
    #sys.exit(main(sys.argv[1:]))
    sys.exit(main(sys.argv))
