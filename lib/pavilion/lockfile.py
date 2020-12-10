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
        self._last_renew = time.time()

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
        expiration = None
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
                    time.sleep(self.SLEEP_PERIOD)
                    continue

                if expiration is None:
                    _, _, expiration, _ = self.read_lockfile()

                if expiration is None or expiration < time.time():
                    # The file is expired. Try to delete it.
                    try:
                        exp_file = self._lock_path.with_name(
                            self._lock_path.name + '.expired'
                        )

                        with LockFile(exp_file):
                            try:
                                self._lock_path.unlink()
                            except OSError:
                                pass
                    except TimeoutError:
                        # Only try this once.
                        expiration = time.time() + NEVER

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

    def renew(self):
        """Renew a lockfile that's been acquired by touching the file. This
        rate limits the renewal to not be overly stressful on the filesystem."""

        now = time.time()

        if self._timeout is None or self._last_renew + self._timeout/2 < now:
            return

        self._last_renew = now
        try:
            self._lock_path.touch()
        except OSError:
            pass

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
        file_note = ",".join([os.uname()[1], utils.get_login(), str(expires),
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
            with self._lock_path.open() as lock_file:
                data = lock_file.read()

            try:
                host, user, expiration, lock_id = data.split(',')
                expiration = float(expiration)
            except ValueError:
                LOGGER.warning("Invalid format in lockfile '%s': %s",
                               self._lock_path, data)
                return None, None, 0, None

            try:
                expiration = expiration + self._lock_path.stat().st_mtime
            except OSError:
                expiration = 0

        except (OSError, IOError):
            return None, None, None, None

        return host, user, expiration, lock_id
