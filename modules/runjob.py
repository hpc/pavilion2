

""" this stand-alone program supports running jobs for any scheduler type
"""

import sys,os
import time
import datetime
import json

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



        
def main(args):

    """ performs the task of running the job defined by the args sent to this handler.
        There may be no terminal associated with this program so all output from the job
        is now directed to a corresponding log file. This program
        functions loosely like the setUpandRun wrapper script from Gazebo.
    """

    params = json.loads(args[2])
    params = convert(params)
    name = args[1]

    # build a unique log file name
    filename = "./" + name + ".log"


    with open(filename, "w+") as f:
        with stdout_redirected(f):
                
            #redirect STDERR to the same file
            sys.stderr = f

            #print "input:"
            #print args, "\n"

            # Load the correct JobController module for this job/test
            jc = load_jcmod(name, params)

            # Instantiate the JobController Object
            this_job = jc(name,params)

            # do what every job has to do
            print name, 'Starting @ ', datetime.datetime.now()
            if params['build']['build_before_run_flag']:
                print "<build-start> ", datetime.datetime.now()
                this_job.build()
                print "<build-end> ", datetime.datetime.now()
            print "<job-start> " , datetime.datetime.now()
            this_job.start()
            print "<job-end> " , datetime.datetime.now()
            this_job.cleanup()




# this gets called if it's run as a script/program
if __name__ == '__main__':
    #sys.exit(main(sys.argv[1:]))
    sys.exit(main(sys.argv))
