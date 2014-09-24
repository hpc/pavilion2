#!python
"""  Implementation raw Job Control mechanism  """

import sys,os
import subprocess
from basejobcontroller import BaseJobController


class RawJobController(BaseJobController):
    """ class to run a test using no scheduler or special launcher """

    def start(self):

        # create own unique working space for this run
        self.setup_working_space()

        # print the common log settings here right after the job is started
        self.save_common_settings()

        # save some info so that scripts may use later on.
        self.setup_job_info()

        # build the exact command to run
        cmd = "cd " + os.environ['PV_RUNHOME'] + "; " + \
            os.environ['PV_SRC_DIR'] + "/scripts/mytime ./" + self.configs['run']['cmd']
        print "\n ->  RawJobController: invoke %s" % cmd

        # Get any buffered output into the output file now
        # so that the the order doesn't look all mucked up
        sys.stdout.flush()

        # Invoke the cmd and send the output to the file setup when
        # the object was instantiated

        self.logger.info(self.lh + " run: " + cmd)
        p = subprocess.Popen(cmd, stdout=self.job_log_file, stderr=self.job_log_file, shell=True)
        # wait for the subprocess to finish
        output, errors = p.communicate()

        if p.returncode or errors:
            print "Error: something went wrong!"
            print [p.returncode, errors, output]
            self.logger.info(self.lh + " run error: " + errors)

        # The post_complete file needs to be placed in the results dir
        # for Gazebo compatibility
        pcf = os.environ["PV_JOB_RESULTS_LOG_DIR"] + "/post_complete"
        text_file = open(pcf, "w")
        text_file.write("{}\n".format("command complete"))
        self.run_epilog()
        text_file.write("{}\n".format("epilog complete"))
        self.cleanup()
        text_file.write("{}\n".format("cleanup complete"))
        text_file.close()

        print "<end>", self.now()

        # The trend_data file needs to be placed in the results dir
        # for Gazebo compatibility
        BaseJobController.process_trend_data()
    
# this gets called if it's run as a script/program
if __name__ == '__main__':

    sys.exit()