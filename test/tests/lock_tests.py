import grp
import os
import pathlib
import subprocess as sp
import time
import io
import time
from threading import Thread
from typing import List

from pavilion import lockfile
from pavilion.unittest import PavTestCase


# NOTE: The lockfile class is designed to work over NFS, but these tests don't
# actually check for that.
class TestLocking(PavTestCase):

    def set_up(self):
        self.lock_path = self.pav_cfg.working_dir/'lock_test.lock'
        self.lock_dir = self.pav_cfg.working_dir/'fuzzy_test.lock'

        if self.lock_path.exists():
            self.lock_path.unlink()

        if self.lock_dir.exists():
            for f in self.lock_dir.iterdir():
                f.unlink()

            self.lock_dir.rmdir()

    def tear_down(self):
        pass

    def test_locks(self):

        # Make sure the lock can be created and deleted with no contention
        # and in non-blocking mode.
        with lockfile.LockFile(self.lock_path):
            # Make sure the lock was created.
            self.assertTrue(self.lock_path.exists())
        # Make sure the lock is deleted after close.
        self.assertFalse(self.lock_path.exists())

        dmy_lock = lockfile.LockFile(self.lock_path, expires_after=100)
        dmy_lock._create_lockfile()

        # Remove the lockfile after 1 second of trying.
        sp.call("sleep 1; rm {}".format(self.lock_path), shell=True)
        # Test waiting for the lockfile.
        with lockfile.LockFile(self.lock_path, timeout=2):
            pass

        # Making sure that we can automatically acquire and delete an
        # expired lockfile.
        very_expired = lockfile.LockFile(
            self.lock_path,
            expires_after=-100)
        very_expired._create_lockfile()
        with lockfile.LockFile(self.lock_path, timeout=1):
            pass

        # Lock objects are reusable.
        lock = lockfile.LockFile(self.lock_path)
        with lock:
            pass
        with lock:
            pass

        # Make sure we can set the group on the lockfile.
        # We need a group other than our default.
        groups = os.getgroups()
        if os.getuid() != 0:
            # This is only valid for non-root users.
            if os.getuid() in groups:
                groups.remove(os.getuid())

            if groups:
                group = groups.pop()
                with lockfile.LockFile(self.lock_path,
                                       group=grp.getgrgid(group).gr_name):
                    stat = self.lock_path.stat()
                    self.assertEqual(stat.st_gid, group)
                    self.assertEqual(stat.st_mode & 0o777,
                                     lockfile.LockFile.LOCK_PERMS)

    def test_lock_contention(self):

        proc_count = 6
        procs = []

        fight_path = pathlib.Path(__file__).parent/'lock_fight.py'

        try:
            for p in range(proc_count):
                procs.append(sp.Popen(['python3',
                                       str(fight_path),
                                       str(self.lock_path)]))
            # Give the procs a chance to start.
            time.sleep(0.5)

            # Get the lock 5 times, hold it a sec, and verify that it's
            # uncorrupted.
            for i in range(5):
                with lockfile.LockFile(self.lock_path, timeout=2) as lock:
                    time.sleep(1)
                    host, user, expires, lock_id = lock.read_lockfile()

                    self.assertTrue(host is not None)
                    self.assertTrue(user is not None)
                    self.assertTrue(expires is not None)
                    self.assertEqual(lock_id, lock._id)
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

        # The lock should time out properly.
        timeout_lock = lockfile.LockFile(self.lock_path, expires_after=100)
        timeout_lock._create_lockfile()
        self.assertRaises(TimeoutError, _acquire_lock, timeout=0.2)
        self.lock_path.unlink()

        # This shouldn't cause an error, but should get logged.
        errfile = io.StringIO()
        with lockfile.LockFile(self.lock_path, errfile=errfile):
            self.lock_path.unlink()
        self.assertIn("mysteriously disappeared", errfile.getvalue())

        dmy_lock = lockfile.LockFile(self.lock_path, expires_after=100)
        dmy_lock._id = 'abcd'
        errfile = io.StringIO()
        with lockfile.LockFile(self.lock_path, errfile=errfile):
            self.lock_path.unlink()
            dmy_lock._create_lockfile()
        # Remove our bad lockfile
        self.lock_path.unlink()
        self.assertIn("mysteriously replaced", errfile.getvalue())

    def test_fuzzylock(self):
        # Test that FuzzyLock object correctly excludes concurrent access

        num_threads = 3
        sleep_time = 0.1
        repeats = 10

        # Check simple mutual exclusion
        with self.assertRaises(TimeoutError):
            with lockfile.FuzzyLock(self.lock_dir):
                with lockfile.FuzzyLock(self.lock_dir, timeout=3):
                    ...

        # Make sure they removed the lock directory
        self.assertFalse(self.lock_dir.exists(), msg='Lock directory was not removed upon exiting lock context.')

        # Clean up previous test
        for f in self.lock_dir.iterdir():
            f.unlink()

        def sleep_lock(idx: int, acquired: List[int], cleaned_up: List[int]) -> None:
            """Simultaneously test that all threads finish running and properly remove
            their lockfiles."""
            with lockfile.FuzzyLock(self.lock_dir, timeout=10) as lock:
                acquired[idx] = True
                self.assertTrue(self.lock_dir.exists(), msg='Lock directory is missing')
                time.sleep(sleep_time)

            # Did the thread remove its lockfile?
            cleaned_up = not self._lockfile.exists()

        # Do this several times to account for indeterminacy
        for _ in range(repeats):

            if self.lock_dir.exists():
                for f in self.lock_dir.iterdir():
                    f.unlink()

            threads = []
            acquired = [False] * num_threads
            cleaned_up = acquired[:]

            for i in range(num_threads):
                thread = Thread(target=sleep_lock, args=(i, acquired, cleaned_up))
                threads.append(thread)
                thread.start()

            for t in threads:
                t.join()

            self.assertTrue(all(acquired), msg='Not all threads acquired the lock.')
            self.assertTrue(all(cleaned_up), msg='Not all threads cleaned up their lockfiles.')
