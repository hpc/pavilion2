#!python
""" skeleton example plug-in that implements a new command 
"""

import sys
import logging

from yapsy.IPlugin import IPlugin

#sys.path.append('/Users/cwi/VWE/modules')


class PluginOne(IPlugin):
    """ This is an example plugin that implements a command called f1 """

    def __init__(self):

        my_name = self.__class__.__name__

        # To log output from this class to to the
        # main (pth) log file you tack it's name onto the pth name space
        self.logger = logging.getLogger('pth.' + my_name)
        self.logger.info('created instance of plugin: %s'% my_name)


    # Every plug-in (command) MUST have a method by the name "cmd".
    # It will be what is called when that command is selected.
    def add_parser_info(self, subparser): 
        parser_f1 = subparser.add_parser("f1", help="f1 help message")
        parser_f1.add_argument('-c', type=int, default=1, help='repeat command Count times')
        parser_f1.set_defaults(sub_cmds='f1')
        return ('f1')

    # Every plugin class MUST have a method by the name "cmd"
    # It will get invoked when sub-command is selected
    def cmd(self, args):
        print "running f1 with:"
        print "args -> %s" % args
        
        # handle the count argument
        count = args['c']
        print "I should run %s times" % count


if __name__=="__main__":
    print PluginOne.__doc__
