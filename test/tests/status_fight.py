# This file isn't a test, but is run as part of the status file tests.
# It writes a whole bunch of status updates to a file over the period of a half
# second, starting when the file is created.

import logging
import os
import sys
import time
from pathlib import Path

log_dir = Path('/tmp', os.getlogin())
if not log_dir.exists():
    os.makedirs(log_dir.as_posix())
logging.basicConfig(filename=(log_dir/'pavilion_tests.log').as_posix())

package_root = Path(__file__).resolve().parents[2]
sys.path.append((package_root/'lib').as_posix())

from pavilion import status_file

TIME_LIMIT = 0.5

# This takes a file name as a single argument.
path = Path(sys.argv[1])

start_time = None

while not path.exists():
    continue

time_limit = time.time() + TIME_LIMIT
status = status_file.StatusFile(path)

while time.time() < time_limit:
    for i in range(100):
        status.set(status_file.STATES.RUNNING,
                   "Testing {}".format(os.getpid()))
