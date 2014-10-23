#!/usr/bin/env python
""" Make base line result averages from the output of the get_results command
"""


# Input:  stdin stream of lines with, hopefully, trend data lines included
#  ex. of an input line that will be matched:
#    Test4.2x32(10 1024) jid(109959) 2014-09-04T08:43:22-0600 avg_iterTime 0.002910 sec
#  then morphed down to:
#    Test4.2x32(10 1024) avg_iterTime 0.002910 sec
# Output:

import sys
import re

print "Making baseline averages with data from:"
for line in sys.stdin:
    searchObj = re.search(r'jid\(', line, re.M | re.I)
    if searchObj:
        # Do some substitution work here, see comments above
        #info = re.sub(r'\S*jid.*-\d+\s', "", line)
        info = re.sub(r'\S*jid.*:[\d-]+\s', "", line)
        print info,

if __name__ == '__main__':
    sys.exit()
