# This file isn't a test, but is run as part of the lock_tests.
# It acquires a lock (given by sys.arg[1]), and repeatedly tries to acquire the lock
# and hold it for a moment.
# It runs until killed.

import logging

import os
import sys
import time
import subprocess

def get_login():
    """Get the current user's login, either through os.getlogin or
    the environment, or the id command."""

    try:
        return os.getlogin()
    except OSError:
        pass

    if 'USER' in os.environ:
        return os.environ['USER']

    try:
        name = subprocess.check_output(['id', '-un'],
                                       stderr=subprocess.DEVNULL)
        return name.decode('utf8').strip()
    except Exception:
        raise RuntimeError(
            "Could not get the name of the current user.")

log_dir = '/tmp/{}'.format(get_login())
if not os.path.exists(log_dir):
    os.makedirs(log_dir)
logging.basicConfig(filename=os.path.join(log_dir, 'pavilion_tests.log'))

package_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
sys.path.append(os.path.join(package_root, 'lib'))

from pavilion import lockfile

while True:
    try:
        with lockfile.LockFile(sys.argv[1], timeout=0.5) as lock:
            time.sleep(0.01)
        # If we don't sleep, the sem proc will probably get the lock right back.
        time.sleep(0.2)
    except TimeoutError:
        continue
