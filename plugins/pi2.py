#!python
""" example of plug-in that implements a feature
"""

import sys
from yapsy.IPlugin import IPlugin


class PluginTwo(IPlugin):
    """ This is plugin 2 that implements Feature 2 """

    def print_name(self):
        print "Plugin 2 loaded!"

    # Every plugin class MUST have a method by the name "add_parser_info"
    # and must return the name of the this sub-command

    def add_parser_info(self, subparser): 
        parser_f2 = subparser.add_parser("f2", help="f2 help message")
        parser_f2.set_defaults(sub_cmds='f2')
        return ('f2')
        
    # Every plugin class MUST have a method by the name "cmd"
    # It will get invoked when sub-command is selected

    def cmd(self, args):
        print "running function f2 with:"
        print "args -> %s" % args


if __name__=="__main__":
    print PluginTwo.__doc__
