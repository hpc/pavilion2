#!/usr/bin/env python

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


""" this stand-alone program supports running jobs for any scheduler type
"""

import sys
import os
import datetime
import json
import logging
import errno
import platform


def convert(inp):
    if isinstance(inp, dict):
        return {convert(key): convert(value) for key, value in inp.iteritems()}
    elif isinstance(inp, list):
        return [convert(element) for element in inp]
    elif isinstance(inp, unicode):
        return inp.encode('utf-8')
    else:
        return inp

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


def load_jcmod(eid, params):

    """
        Basically trying to dynamically load the correct job controller
        (perform a 'from typejobcontroller import TypeJobController')
    """

    # build with a known naming convention
    module_name = params['run']['scheduler'] + "jobcontroller"
    class_name_cc = params['run']['scheduler'].title() + "JobController"

    sys.path.append("/modules")

    try:

        # dynamically import the desired module
        mh = __import__(module_name)

    except:
        print "Warning: no job controller for scheduler type %s" % params['run']['scheduler']
        print "  Skipping job %s" % eid
        return

    # get a reference to the JobController class
    class_ = getattr(mh, class_name_cc)
    return class_


def build_results_dir(params):

    """ function to create the final result directory for a job/test.
        Intent is to make backwards compatible with Gazebo.
    """
    logger = logging.getLogger('pav.runjob.build_results_dir')
    lh = params['log_handle']

    root_result_dir = params['results']['root']
    name = params['name']
    new_dir = root_result_dir + "/gzshared/"
    date_parts = datetime.datetime.now().strftime("%Y/%Y-%m/%Y-%m-%d/")
    target = platform.uname()[1].split(".", 1)[0]
    new_dir = new_dir + date_parts + target + "/" + name + "/"
    pid = str(os.getpid())
    results_now = datetime.datetime.now()
    ld = name + "__" + params['run']['cmd'].split(".", 1)[0] + \
        "__" + pid + "__" + target  \
        + "." + results_now.strftime('%Y-%m-%dT%H:%M:%S:%f')
    new_dir += ld

    logger.info("Make log directory: " + new_dir)
    try:
        os.umask(0o002)
        os.makedirs(new_dir, 0o775)
    except OSError as e:
        if e.errno == errno.EEXIST:
            logger.info(lh + " Error, somehow log directory exists!, skipping job! : \n\t" + new_dir)
            pass
        else:
            logger.info(lh + " Error, cannot create log directory, skipping job! : \n\t" + new_dir)
            raise

    return new_dir


def now():
    return " " + datetime.datetime.now().strftime("%m-%d-%YT%H:%M:%S")

        
def main(args):

    """ performs the task of running the job defined by the args sent to this handler.
        There may be no terminal associated with this program so all output from the job
        is now directed to a corresponding log file.
    """
    entry_id = args[1]
    params = json.loads(args[2])
    params = convert(params)
    ml_file = args[3]

    logger = logging.getLogger('pav.runjob')
    logger.setLevel(logging.DEBUG)
    fh = logging.FileHandler(filename=ml_file)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # This handle "name(pid)" can be used to follow all activity of this
    # specific job thread in the pav.log file
    test_name = params['name']
    logger_name = entry_id + "-" + test_name + "(" + str(os.getpid()) + ")"
    params['log_handle'] = logger_name
    lh = params['log_handle']

    # Load the correct JobController module for this specific job/test
    jc = load_jcmod(entry_id, params)
    logger.info(lh + ": loaded %s jobcontroller " % params['run']['scheduler'])

    # all STDOUT and STDERR from job directed to its own log file
    results_dir = build_results_dir(params)
    os.environ["PV_JOB_RESULTS_LOG_DIR"] = results_dir

    logfile = results_dir + "/" + test_name + ".log"
    os.environ["PV_JOB_RESULTS_LOG"] = logfile
    logger.info(lh + ": logfile -> %s" % logfile)

    with open(logfile, "w+") as lf:
        with stdout_redirected(lf):

            # redirect STDERR to the same file
            sys.stderr = lf

            try:
                # instantiate job controller object
                print params
                this_job = jc(entry_id, params, lf)
            except RuntimeError, err:
                logger.error(lh + "Error: skipping job! " + err.message)
                return
            except:
                logger.error(lh + 'Error: job start problem, skipping job! (Hint: look in job output log)')
                print "Error: ", sys.exc_info()[0]
                print "  --> ", sys.exc_info()[1]
                return

            # do what every job has to do
            if params['build']['build_before_run_flag']:
                logger.info(lh + " build-start ")
                print "<build-start> ", now()
                this_job.build()
                logger.info(lh + " build-end ")
                print "<build-end> ", now()

            logger.info(lh + " starting")
            print "<start>", now()
            this_job.start()
            #print "<end>" , now()
            logger.info(lh + ' Submit completed ')


# this gets called if it's run as a script from the shell
if __name__ == '__main__':
    sys.exit(main(sys.argv))
