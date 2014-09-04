#!/usr/bin/env python
""" Make box plots from the output of the get_results command"""

import sys
import os


for line in sys.stdin:
    print line

if __name__ == '__main__':
    # pass entire command line to main except for the command name
    sys.exit()
