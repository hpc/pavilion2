from __future__ import print_function, unicode_literals, division

import grp
from pavilion import lockfile
import os
import subprocess as sp
import sys
import time
import unittest


# NOTE: The lockfile class is designed to work over NFS, but these tests don't actually check for
#  that.
class TestConfig(unittest.TestCase):
    lock_path = 'lock_test.lock'

    def setUp(self):
        if os.path.exists(self.lock_path):
            print("\nRemoving lockfile {} from old (failed) run.".format(self.lock_path),
                  file=sys.stderr)
            os.unlink(self.lock_path)

    def test_locks(self):

        # Make sure the lock can be created and deleted with no contention and in non-blocking mode.
        with lockfile.LockFile(self.lock_path):
            # Make sure the lock was created.
            self.assertTrue(os.path.exists(self.lock_path))
        # Make sure the lock is deleted after close.
        self.assertFalse(os.path.exists(self.lock_path))

        lockfile.LockFile._create_lockfile(self.lock_path, 100, '1234')

        # Remove the lockfile after 1 second of trying.
        sp.call("sleep 1; rm {}".format(self.lock_path), shell=True)
        # Test waiting for the lockfile.
        with lockfile.LockFile(self.lock_path, timeout=2):
            pass

        # Making sure that we can automatically acquire and delete an expired lockfile.
        lockfile.LockFile._create_lockfile(self.lock_path, -100, '1234')
        with lockfile.LockFile(self.lock_path, timeout=1):
            pass

        # Lock objects are reusable.
        lock = lockfile.LockFile(self.lock_path)
        with lock:
            pass
        with lock:
            pass

        os.getgid()


        # Make sure we can set the group on the lockfile.
        # We need a group other than our default.
        groups = os.getgroups()
        groups.remove(os.getuid())
        if not groups:
            print("Could not test group permissions with lockfile, no suitable alternate group "
                  "found.", file=sys.stderr)
        else:
            group = groups.pop()
            with lockfile.LockFile(self.lock_path, group=grp.getgrgid(group).gr_name):
                stat = os.stat(self.lock_path)
                self.assertEqual(stat.st_gid, group)
                self.assertEqual(stat.st_mode & 0777, 0774)

    def test_lock_contention(self):

        proc_count = 6
        procs = []

        try:
            for p in range(proc_count):
                procs.append(sp.Popen(['python', 'tests/lock_fight.py', self.lock_path]))
            # Give the procs a chance to start.
            time.sleep(0.5)

            # Get the lock 5 times, hold it a sec, and verify that it's uncorrupted.
            for i in range(5):
                with lockfile.LockFile(self.lock_path, timeout=2) as lock:
                    # print("Test - {} got lock {}".format(os.getpid(), lock._id))
                    time.sleep(1)
                    host, user, expires, id = lock.read_lockfile()

                    self.assertTrue(host is not None)
                    self.assertTrue(user is not None)
                    self.assertTrue(expires is not None)
                    self.assertEqual(id, lock._id)
                    # print("Test - {} bye lock {}".format(os.getpid(), lock._id))
                # Let the other procs get the lock this time.
                time.sleep(0.2)

        finally:
            # Make sure we kill all the subprocesses.
            for proc in procs:
                proc.terminate()
                proc.kill()

    def test_lock_errors(self):

        def _acquire_lock(*args, **kwargs):
            with lockfile.LockFile(self.lock_path, *args, **kwargs):
                pass

        # We can't acquire the lock more than once at a time.
        with lockfile.LockFile(self.lock_path):
            self.assertRaises(RuntimeError, _acquire_lock)

        # The lock should time out properly.
        lockfile.LockFile._create_lockfile(self.lock_path, 100, '1234')
        self.assertRaises(lockfile.TimeoutError, _acquire_lock, timeout=0.2)
        os.unlink(self.lock_path)

        # This shouldn't cause an error, but should get logged.
        with lockfile.LockFile(self.lock_path):
            os.unlink(self.lock_path)

        with lockfile.LockFile(self.lock_path):
            os.unlink(self.lock_path)
            lockfile.LockFile._create_lockfile(self.lock_path, 100, 'abcd')
        # Remove our bad lockfile
        os.unlink(self.lock_path)

