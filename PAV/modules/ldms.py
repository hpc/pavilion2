#!python

""" plug-in that supports using the LDMS tool 
"""

import os
import sys
import subprocess
import datetime
import logging


class LDMS():

    def __init__(self, my_te):
        my_name = self.__class__.__name__
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('initialize %s to run: ' % my_name)

        self.pid = str(os.getpid())
        self.lh = my_name

        params = my_te.get_values()
        self.name = my_te.get_name()
        self.install_dir = str(params['ldms']['install_dir'])
        self.start_cmd = str(params['ldms']['start_cmd'])
        self.output_dir_root = str(params['ldms']['output_dir_root'])
        self.freq = params['ldms']['freq']
        self.metric_list = str(params['ldms']['metric_list'])

        self.output_dir = self.create_output_dir()

    def create_output_dir(self):
        # This dir must be created before LDMS starts and should
        # be unique so that each new test run does not stomp on
        # existing data from a prior one.

        sub_dir = self.name + "-" + datetime.datetime.now().strftime('%H:%M:%S%f')
        if "HOME" in self.output_dir_root:
            root = os.environ['HOME']
        else:
            root = self.output_dir_root
        output_dir = root + "/ldmsData/" + sub_dir

        self.logger.info(self.lh + " Make metrics directory: " + output_dir)
        try:
            os.umask(0o002)
            os.makedirs(output_dir, 0o755)
        except OSError:
            print " Error creating metrics directory : \n\t" + output_dir
            self.logger.info(self.lh + " Error creating metrics directory! : \n\t" + output_dir)
            output_dir = ''
            pass

        print "Created ldms metrics dir: " + output_dir

        return output_dir

    def get_output_dir(self):
        return self.output_dir

    def get_start_cmd(self):
        full_cmd = self.install_dir + "/" + self.start_cmd
        full_cmd += " -f " + str(self.freq)
        full_cmd += " -m " + self.metric_list
        full_cmd += " -s " + self.output_dir
        return full_cmd

    # define some static methods for LDMS job control

    @staticmethod
    def start(cmd):
        # start and don't wait. Report success or fail in the log(s).

        try:
            output = subprocess.check_output(cmd, shell=True)
            print output
        except subprocess.CalledProcessError as e:
            ret = e.returncode
            if ret in (1, 2):
                print("the command failed")
            elif ret in (3, 4, 5):
                print("the command failed very much")
            pass


    @staticmethod
    def status(jid):
        pass

    @staticmethod
    def stop(jid):
        pass



if __name__ == "__main__":
    print LDMS.__doc__
