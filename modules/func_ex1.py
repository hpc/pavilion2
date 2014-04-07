#!python
""" example of module that implements function 1
"""

import sys

def help_me():
    """ return help info from func 1"""
    print "I'm of no use :("



if __name__=="__main__":
    print help_me.__doc__
