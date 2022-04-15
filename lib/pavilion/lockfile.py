"""Pavilion uses lock files to handle concurrency across multiple nodes
and systems. It has to assume the file-system that these are written
to has atomic, O_EXCL file creation. """

import grp
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Union, TextIO
import threading

from pavilion import output
from pavilion import utils

# Expires after a silly long time.
NEVER = 10**10


class LockFile:
    """An NFS friendly way to create a lock file. Locks contain information
on what host and user created the lock, and have a built in expiration
date. To be used in a 'with' context.

In general, you should use a short expire period if possible and '.renew()' the
lock regularly while it's in use for longer periods of time.

:cvar int DEFAULT_EXPIRE: Time till file is considered stale, in seconds. (3
    seconds by default)
:cvar int SLEEP_PERIOD: How long to sleep between lock attempts.
    This shouldn't be any less than 0.01 or so on a regular filesystem.
    0.2 is pretty reasonable for an nfs filesystem and sporadically used
    locks.
:cvar int LOCK_PERMS: Default lock permissions
"""

    DEFAULT_EXPIRE = 3

    SLEEP_PERIOD = 0.2

    LOCK_PERMS = 0o774

    # How long to wait before printing user notifications about potential
    # problems.
    NOTIFY_TIMEOUT = 5

    def __init__(self, lockfile_path: Path, group: str = None, timeout: float = None,
                 expires_after: int = DEFAULT_EXPIRE, errfile: TextIO = sys.stderr):
        """Initialize the lock file. The resulting class can be reused
        multiple times.

:param lockfile_path: The path to the lockfile. Should
    probably start with a '.', and end with '.lock', but that's up to
    the user.
:param group: The name of the group to set lockfiles to. If
    this is given,
:param timeout: When to quit trying to acquire the lock in seconds.
    None (default) denotes non-blocking mode.
:param expires_after: When to consider the lock dead,
    and overwritable (in seconds). The NEVER module variable is
    provided as easily named long time. (10^10 secs, 317 years)
:param errfile: File object to print errors to.
"""

        self.lock_path = Path(lockfile_path)
        self._timeout: Union[float, None] = timeout
        self.expire_period = expires_after
        if expires_after is None:
            raise ValueError("Invalid value for 'expires_after'. Value must be an int/float. "
                             "Use lockfile.NEVER for a non-expiring lock.")
        self._group = None
        self._last_renew = time.time()
        self._errfile = errfile

        if group is not None:
            # This could error out, but should be checked by pavilion
            # separately.
            try:
                self._group = grp.getgrnam(group).gr_gid
            except KeyError:
                raise KeyError("Unknown group '{}' when creating lock '{}'."
                               .format(group, lockfile_path))

        self._open = False

        self._id = str(uuid.uuid4())

    def lock(self):
        """Try to create and lock the lockfile."""

        if self._open:
            raise RuntimeError("Trying to open a lock multiple times.")

        start = time.time()
        acquired = False
        first = True
        notified = False

        # Try until we timeout (at least once).
        while (self._timeout is None or first or
               time.time() - self._timeout <= start):

            first = False
            try:

                self._create_lockfile()
                acquired = True

                # We got the lock, quit the loop.
                break

            except (OSError, IOError):
                try:
                    # This is a race against file deletion by the lock holder.
                    lock_stat = self.lock_path.stat()
                except (FileNotFoundError, OSError):
                    time.sleep(self.SLEEP_PERIOD)
                    continue

                _, _, expiration, _ = self.read_lockfile()

                if expiration is not None and expiration < time.time():
                    # The file is expired. Try to delete it.
                    exp_file = self.lock_path.with_name(
                        self.lock_path.name + '.expired')
                    try:

                        with LockFile(exp_file, timeout=3, expires_after=NEVER):

                            # Make sure it's the same file as before we checked
                            # the expiration.
                            try:
                                lock_stat2 = self.lock_path.stat()
                            except (FileNotFoundError, OSError):
                                continue

                            if (lock_stat.st_ino != lock_stat2.st_ino or
                                    lock_stat.st_mtime != lock_stat2.st_mtime):
                                continue

                            try:
                                self.lock_path.unlink()
                            except OSError:
                                pass
                    except TimeoutError:
                        # If we can't get the lock within 3 seconds, just
                        # delete the expired lock if it exists.
                        try:
                            exp_file.unlink()
                        except OSError:
                            pass
                    except OSError:
                        pass
                else:
                    # The lockfile isn't expired yet, so wait.
                    time.sleep(self.SLEEP_PERIOD)

            if not notified and (start + self.NOTIFY_TIMEOUT < time.time()):
                notified = True
                self._warn("Waiting for lock '{}'.".format(self.lock_path))

        if not acquired:
            raise TimeoutError("Lock on file '{}' could not be acquired."
                               .format(self.lock_path))

        return self

    def unlock(self):
        """Delete the lockfile, thereby releasing the lock.

:raises RuntimeError: When we can't delete our own lockfile for some
    reason.
"""

        # There isn't really anything we can do in this case.
        host, user, _, lock_id = self.read_lockfile()

        if lock_id is not None and lock_id != self._id:
            # The lock has been replaced by a different one already.
            self._warn("Lockfile '{}' mysteriously replaced with one from {}."
                       .format(self.lock_path, (host, user)))
        else:
            try:
                self.lock_path.unlink()
            except OSError as err:
                # There isn't really anything we can do in this case.
                host, user, _, lock_id = self.read_lockfile()

                if lock_id == self._id:
                    self._warn("Lockfile '{}' could not be deleted: '{}'"
                               .format(self.lock_path, err))
                else:
                    self._warn("Lockfile '{}' mysteriously disappeared."
                               .format(self.lock_path))

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.unlock()

    def __enter__(self):
        return self.lock()

    def renew(self):
        """Renew a lockfile that's been acquired by touching the file. This
        rate limits the renewal to not be overly stressful on the filesystem."""

        now = time.time()

        if self.expire_period is None or self._last_renew + self.expire_period/2 < now:
            return

        self._last_renew = now
        try:
            self.lock_path.touch()
        except OSError:
            pass

    def _create_lockfile(self):
        """Create and fill out a lockfile at the given path.

        :returns: None
        :raises IOError: When the file cannot be written too.
        :raises OSError: When the file cannot be opened or already exists.
        """

        # DEV NOTE: This logic is separate so that we can create these files
        # outside of the standard mechanisms for testing purposes.

        # We're doing low level operations on the path, so we just need
        # it as a string.
        # Note that this is not atomic, so anything that reads the contents
        # needs to handle empty files specially.
        path = str(self.lock_path)

        file_note = ",".join([os.uname()[1], utils.get_login(), str(self.expire_period),
                              self._id])
        file_note = file_note.encode('utf8')
        file_num = os.open(path, os.O_EXCL | os.O_CREAT | os.O_RDWR)
        os.write(file_num, file_note)
        os.close(file_num)

        try:
            os.chmod(path, self.LOCK_PERMS)
        except OSError as err:
            self._warn("Lockfile at '{}' could not set permissions: {}".format(path, err))

        if self._group is not None:
            try:
                os.chown(path, os.getuid(), self._group)
            except OSError as err:
                self._warn("Lockfile at '{}' could not set group: {}".format(path, err))

    def read_lockfile(self):
        """Returns the components of the lockfile content, or None for each of
these values if there was an error..

:returns: host, user, expiration (as a float), id
"""

        try:
            with self.lock_path.open() as lock_file:
                data = lock_file.read()

            try:
                mtime = self.lock_path.stat().st_mtime
            except OSError:
                mtime = 0

            try:
                host, user, expiration, lock_id = data.split(',')
                expiration = float(expiration) + mtime
            except ValueError:
                # This usually happens when a lockfile is very new, and hasn't had
                # its data written yet. Give it a moment...
                return None, None, mtime + 3, None

        except (OSError, IOError):
            # Couldn't read the lockfile, so try again later.
            return None, None, None, None

        return host, user, expiration, lock_id

    def _warn(self, msg):
        """Issue a warning message."""

        output.fprint(self._errfile, msg, color=output.YELLOW)


class LockFilePoker:
    """This context creates a thread that regularly 'pokes' a lockfile to make sure it
    doesn't expire."""

    def __init__(self, lockfile: LockFile):
        self._lockfile = lockfile
        self._done_event = threading.Event()
        self._done_event.clear()
        self._thread = None

    def __enter__(self):
        """Create a thread to poke the lock file."""

        sleep_time = self._lockfile.expire_period / 3

        def lock_file_poker():
            """Renew the lockfile continuously."""

            while True:
                if not self._done_event.wait(timeout=sleep_time):
                    self._lockfile.renew()
                else:
                    break

        self._thread = threading.Thread(target=lock_file_poker)
        self._thread.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Destroy/join the pokey thread."""

        self._done_event.set()
        self._thread.join()
