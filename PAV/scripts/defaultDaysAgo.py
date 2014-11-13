#!/usr/bin/env python

"""
  print the date 15 days ago
"""

import datetime

today = datetime.date.today()
#print 'Today    :', today

delta_day = datetime.timedelta(days=15)

daysago = today - delta_day
#print 'Daysago:', daysago 
print daysago 
