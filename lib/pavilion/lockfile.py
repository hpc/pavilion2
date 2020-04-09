"""Pavilion uses lock files to handle concurrency across multiple nodes
and systems. It has to assume the file-system that these are written
to has atomic, O_EXCL file creation. """

from pathlib import Path
import grp
import logging
import os
import time
import uuid
from pavilion import utils

LOGGER = logging.getLogger('pav.' + __name__)


# Expires after a silly long time.
NEVER = 10**10


class LockFile:
    """An NFS friendly way to create a lock file. Locks contain information
on what host and user created the lock, and have a built in expiration
date. To be used in a 'with' context.

:cvar int DEFAULT_EXPIRE: Time till file is considered stale, in seconds. (5
    minute default)
:cvar int SLEEP_PERIOD: How long to sleep between lock attempts.
    This shouldn't be any less than 0.01 or so on a regular filesystem.
    0.2 is pretty reasonable for an nfs filesystem and sporadically used
    locks.
:cvar int LOCK_PERMS: Default lock permissions
"""

    DEFAULT_EXPIRE = 60 * 60 * 5

    SLEEP_PERIOD = 0.2

    LOCK_PERMS = 0o774

    def __init__(self, lockfile_path, group=None, timeout=None,
                 expires_after=DEFAULT_EXPIRE):
        """Initialize the lock file. The resulting class can be reused
        multiple times.

:param Path lockfile_path: The path to the lockfile. Should
    probably start with a '.', and end with '.lock', but that's up to
    the user.
:param str group: The name of the group to set lockfiles to. If
    this is given,
:param int timeout: When to quit trying to acquire the lock in seconds.
    None (default) denotes non-blocking mode.
:param int expires_after: When to consider the lock dead,
    and overwritable (in seconds). The NEVER module variable is
    provided as easily named long time. (10^10 secs, 317 years)
"""

        self._lock_path = Path(lockfile_path)
        self._timeout = timeout
        self._expire_period = expires_after
        self._group = None

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
        expires = None
        first = True

        # Try until we timeout (at least once).
        while (self._timeout is None or first or
               time.time() - self._timeout <= start):

            first = False
            try:

                self._create_lockfile(
                    self._lock_path,
                    self._expire_period,
                    self._id,
                    group_id=self._group)
                acquired = True

                # We got the lock, quit the loop.
                break

            except (OSError, IOError):
                if self._timeout is None:
                    continue

                if expires is None:
                    _, _, expires, _ = self.read_lockfile()

                    if expires is None:
                        expires = time.time() + NEVER

                if expires < time.time():
                    # The file is expired. Try to delete it.
                    try:
                        exp_file = self._lock_path.with_name(
                            self._lock_path.name + '.expired'
                        )

                        with LockFile(exp_file,
                                      expires_after=NEVER):
                            try:
                                self._lock_path.unlink()
                            except OSError:
                                pass
                    except TimeoutError:
                        pass

                    # Only try this once.
                    expires = time.time() + NEVER
                else:
                    time.sleep(self.SLEEP_PERIOD)

        if not acquired:
            raise TimeoutError("Lock on file '{}' could not be acquired."
                               .format(self._lock_path))

        return self

    def unlock(self):
        """Delete the lockfile, thereby releasing the lock.

:raises RuntimeError: When we can't delete our own lockfile for some
    reason.
"""

        # There isn't really anything we can do in this case.
        host, user, _, lock_id = self.read_lockfile()

        if lock_id is not None and lock_id != self._id:
            LOGGER.error(
                "Lockfile '%s' mysteriously replaced with one from %s.",
                self._lock_path, (host, user))
        else:
            try:
                self._lock_path.unlink()
            except OSError as err:
                # There isn't really anything we can do in this case.
                host, user, _, lock_id = self.read_lockfile()

                if lock_id == self._id:
                    LOGGER.warning("Lockfile '%s' could not be deleted: '%s'",
                                   self._lock_path, err)
                else:
                    LOGGER.error("Lockfile '%s' mysteriously disappeared.",
                                 self._lock_path)

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.unlock()

    def __enter__(self):
        return self.lock()

    @classmethod
    def _create_lockfile(cls, path, expires, lock_id, group_id=None):
        """Create and fill out a lockfile at the given path.

:param Path path: Where the file will be created.
:param int expires: How far in the future the lockfile expires.
:param str lock_id: The unique identifier for this lockfile.
:returns: None
:raises IOError: When the file cannot be written too.
:raises OSError: When the file cannot be opened or already exists.
"""

        # DEV NOTE: This logic is separate so that we can create these files
        # outside of the standard mechanisms for testing purposes.

        # We're doing low level operations on the path, so we just need
        # it as a string.
        path = str(path)

        file_num = os.open(path, os.O_EXCL | os.O_CREAT | os.O_RDWR)
        expiration = time.time() + expires
        file_note = ",".join([os.uname()[1], utils.get_login(), str(expiration),
                              lock_id])
        file_note = file_note.encode('utf8')
        os.write(file_num, file_note)
        os.close(file_num)

        try:
            os.chmod(path, cls.LOCK_PERMS)
        except OSError as err:
            LOGGER.warning("Lockfile at '%s' could not set permissions: %s",
                           path, err)

        if group_id is not None:
            try:
                os.chown(path, os.getuid(), group_id)
            except OSError as err:
                LOGGER.warning("Lockfile at '%s' could not set group: %s",
                               path, err)

    def read_lockfile(self):
        """Returns the components of the lockfile content, or None for each of
these values if there was an error..

:returns: host, user, expiration (as a float), id
"""

        try:
            with self._lock_path.open(mode='r') as lock_file:
                data = lock_file.read()

            try:
                host, user, expiration, lock_id = data.split(',')
                expiration = float(expiration)
            except ValueError:
                LOGGER.warning("Invalid format in lockfile '%s': %s",
                               self._lock_path, data)
                return None, None, None, None

        except (OSError, IOError):
            return None, None, None, None

        return host, user, expiration, lock_id
