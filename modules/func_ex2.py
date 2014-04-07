#!/user/bin/python
"""
example of module that implements function 2
"""

import sys

def help_me():
    """ return help info from function 2 """

    print "No help for you... stupid human!"


if __name__=="__main__":
    print help_me.__doc__
