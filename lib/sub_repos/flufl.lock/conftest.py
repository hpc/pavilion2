import os
import time
import multiprocessing

from sybil import Sybil
from psutil import pid_exists
from doctest import ELLIPSIS, NORMALIZE_WHITESPACE, REPORT_NDIFF
from datetime import timedelta
from tempfile import TemporaryDirectory
from contextlib import ExitStack
from flufl.lock import SEP, Lock
from sybil.parsers.doctest import DocTestParser
from sybil.parsers.codeblock import CodeBlockParser

DOCTEST_FLAGS = ELLIPSIS | NORMALIZE_WHITESPACE | REPORT_NDIFF


def child_locker(filename, lifetime, queue, extra_sleep):
    # First, acquire the file lock.
    with Lock(filename, lifetime):
        # Now inform the parent that we've acquired the lock.
        queue.put(True)
        # Keep the file lock for a while.
        time.sleep(lifetime.seconds + extra_sleep)


def acquire(filename, *, lifetime=None, extra_sleep=-1):
    """Acquire the named lock file in a subprocess."""
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=child_locker,
        args=(filename, timedelta(seconds=lifetime), queue, extra_sleep))
    proc.start()
    while not queue.get():
        time.sleep(0.1)


def child_waitfor(filename, lifetime, queue):
    t0 = time.time()
    # Try to acquire the lock.
    with Lock(filename, lifetime):
        # Tell the parent how long it took to acquire the lock.
        queue.put(time.time() - t0)


def waitfor(filename, lifetime):
    """Fire off a child that waits for a lock."""
    queue = multiprocessing.Queue()
    proc = multiprocessing.Process(
        target=child_waitfor,
        args=(filename, lifetime, queue))
    proc.start()
    return queue.get()


def simulate_process_crash(lockfile):
    # We simulate an unclean crash of the process holding the lock by
    # deliberately fiddling with the pid in the lock file, ensuring that no
    # process with the new pid exists.
    with open(lockfile) as fp:
        filename = fp.read().strip()
    lockfile, hostname, pid_str, random = filename.split(SEP)
    pid = int(pid_str)
    while pid_exists(pid):
        pid += 1
    with open(lockfile, 'w') as fp:
        fp.write(SEP.join((lockfile, hostname, str(pid), random)))


class DoctestNamespace:
    def __init__(self):
        self._resources = ExitStack()

    def setup(self, namespace):
        namespace['acquire'] = acquire
        namespace['temporary_lockfile'] = self.temporary_lockfile
        namespace['waitfor'] = waitfor
        namespace['simulate_process_crash'] = simulate_process_crash

    def teardown(self, namespace):
        self._resources.close()

    def temporary_lockfile(self):
        lock_dir = self._resources.enter_context(TemporaryDirectory())
        return os.path.join(lock_dir, 'test.lck')


namespace = DoctestNamespace()


pytest_collect_file = Sybil(
    parsers=[
        DocTestParser(optionflags=DOCTEST_FLAGS),
        CodeBlockParser(),
        ],
    pattern='*.rst',
    setup=namespace.setup,
    ).pytest()
