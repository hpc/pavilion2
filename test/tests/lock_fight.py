# This file isn't a test, but is run as part of the lock_tests.
# It acquires a lock (given by sys.arg[1]), and repeatedly tries to acquire the lock
# and hold it for a moment.
# It runs until killed.

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

from pavilion import lockfile

while True:
    try:
        with lockfile.LockFile(sys.argv[1], timeout=0.5) as lock:
            # print("Fight {} - got lock {}".format(os.getpid(), lock._id))
            time.sleep(0.01)
            # print("Fight {} - bye lock {}".format(os.getpid(), lock._id))
        # If we don't sleep, the sem proc will probably get the lock right back.
        time.sleep(0.2)
    except lockfile.TimeoutError:
        continue
