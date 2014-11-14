#!/usr/bin/env python

import sys
import datetime

"""
  print the date 'arg' days ago, default to 15
  Created for a Perl script to call...
  author: C. Idler
"""

try:
  days_ago = int(sys.argv[1])
except ValueError:
  # arg supplied not an int
  days_ago = 15
except IndexError:
  # no arg supplied
  days_ago = 15

print datetime.date.today() - datetime.timedelta(days=days_ago) 
