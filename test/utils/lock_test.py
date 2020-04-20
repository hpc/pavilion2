"""Run this simultaniously on multiple hosts that share an NFS filesystem to test cross-system NFS
locking. The tests do a synchronized start at the top of the minute according to the system clock, so 
make sure the system clocks are close (within .5 seconds will do). Any locking errors will be
printed."""

from pavilion import lockfile
from pathlib import Path
import time

acquires = 500
acquired = 0

now = time.time()
# Delay for the rest of the minute
go_time = (now - now%60 + 60)
while time.time() < go_time:
    time.sleep(.01)

acquire_times = []

print('starting', time.time(), flush=True)

# Acquire a bunch of locks to give plenty of chances for things to break.
# More locking attempts also mean more time for runs on multiple systems 
# to overlap.
while acquired < acquires:
    start = time.time()
    with lockfile.LockFile('/usr/projects/hpctest/.locktest'):
        acquire_times.append(time.time() - start)
        print(".", end="", flush=True)
        acquired += 1

print('finished', time.time())
print('avg acquire', sum(acquire_times)/len(acquire_times))
