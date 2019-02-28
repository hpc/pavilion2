# This file isn't a test, but is run as part of the status file tests.
# It writes a whole bunch of status updates to a file over the period of a half
# second, starting when the file is created.

from __future__ import unicode_literals, print_function, division

import logging
import os
import sys
import time

log_dir = '/tmp/{}'.format(os.getlogin())
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
logging.basicConfig(filename=os.path.join(log_dir, 'pavilion_tests.log'))

package_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(os.path.join(package_root, 'lib'))
sys.path.append(os.path.join(package_root, 'lib', 'pavilion', 'dependencies'))

from pavilion import status_file

TIME_LIMIT = 0.5

# This takes a file name as a single argument.
path = sys.argv[1]

start_time = None

while not os.path.exists(path):
    continue

start_time = time.time()
status = status_file.StatusFile(path)

while True:
    if time.time() - start_time > TIME_LIMIT:
        break

    for i in range(100):
        status.set(status_file.STATES.RUNNING, "Testing {}".format(os.getpid()))
