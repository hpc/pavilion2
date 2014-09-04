#!/usr/bin/env python
""" Make box plots from the output of the get_results command"""

import sys
import re

print "Making box plots with data from:"
for line in sys.stdin:
    searchObj = re.search(r'jid\(', line, re.M|re.I)
    if searchObj:
        print line,

if __name__ == '__main__':
    # pass entire command line to main except for the command name
    sys.exit()
