#!/usr/bin/env python
""" Make box plots from the output of the get_results command"""


# Input:  stdin stream of lines with, hopefully, trend data lines included
#  ex. of a valid line is:
#    Test4.2x32(10 1024) jid(109959) 2014-09-04T08:43:22-0600 avg_iterTime 0.002910 sec
# Output: Should be a messaged indicating where output plot files reside

import sys
import re

print "Making box plots with data from:"
for line in sys.stdin:
    searchObj = re.search(r'jid\(', line, re.M | re.I)
    if searchObj:
        # Should do work here, see correct output above
        print line,  # this line for debug purposes

if __name__ == '__main__':
    # pass entire command line to main except for the command name
    sys.exit()
