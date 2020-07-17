"""
Multi-host lockfile test.

Usage: python3 lock_test.py <lockfile_dir>

Run this simultaniously on multiple hosts that share an NFS filesystem 
to test cross-system NFS locking. The tests do a synchronized start at the top 
of the minute according to the system clock, so make sure the system clocks are close 
(within .5 seconds will do). Any locking errors will be
printed.

The shared lockfile is placed in this directory

The test should complete on all systems without errors.

"""

from pathlib import Path
import sys
libdir = (Path(__file__).resolve().parents[2]/'lib').as_posix()
sys.path.append(libdir)

from pavilion import lockfile
import time

lock_dir = None
if len(sys.argv) == 2:
    try:
        lock_dir = Path(sys.argv[1])
    except:
        pass

if ('--help' in sys.argv or '-h' in sys.argv
        or lock_dir is None or not lock_dir.exists()):
    print(__doc__)
    sys.exit(1)

acquires = 500
acquired = 0

now = time.time()
# Delay for the rest of the minute
go_time = (now - now%60 + 60)
while time.time() < go_time:
    time.sleep(.01)

acquire_times = []

print('starting', time.time(), flush=True)

lock_path = lock_dir/'test.lockfile'

# Acquire a bunch of locks to give plenty of chances for things to break.
# More locking attempts also mean more time for runs on multiple systems 
# to overlap.
while acquired < acquires:
    start = time.time()
    with lockfile.LockFile(lock_path):
        acquire_times.append(time.time() - start)
        print(".", end="", flush=True)
        acquired += 1

print('finished', time.time())
print('avg acquire', sum(acquire_times)/len(acquire_times))
