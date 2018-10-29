from __future__ import division, unicode_literals, print_function

import grp
import logging
import os
import time
import uuid

LOGGER = logging.getLogger('pav.' + __name__)

# Time till file is considered stale, in seconds.
DEFAULT_EXPIRE = 60 * 60 * 5

# How long to sleep between lock attempts.
SLEEP_PERIOD = 0.2

# Expires after a silly long time.
NEVER = 10**10


class TimeoutError(RuntimeError):
    """Error raised when the lockfile times out."""
    pass


class LockFile(object):
    """An NFS friendly way to create a lock file."""

    def __init__(self, lockfile_path, group=None, timeout=None, expires_after=DEFAULT_EXPIRE):
        self._lock_path = lockfile_path
        self._timeout = timeout
        self._expire_period = expires_after
        self._group = None

        if group is not None:
            # This could error out, but should be checked by pavilion separately.
            self._group = grp.getgrnam(group).gr_gid

        self._open = False

        self._id = unicode(uuid.uuid4())

    def __enter__(self):
        """Try to create and lock the lockfile."""

        if self._open:
            raise RuntimeError("Trying to open a lock multiple times.")

        start = time.time()
        acquired = False
        expires = None

        # Try until we timeout
        while self._timeout is None or time.time() - self._timeout <= start:
            try:

                self._create_lockfile(self._lock_path, self._expire_period, self._id,
                                      group_id=self._group)
                acquired = True

                # We got the lock, quit the loop.
                break

            except (OSError, IOError):
                if self._timeout is None:
                    raise TimeoutError("Could not acquire lock (non-blocking).")

                if expires is None:
                    _, _, expires, _ = self.read_lockfile()

                    if expires is None:
                        expires = time.time() + NEVER

                if expires < time.time():
                    # The file is expired. Try to delete it.
                    try:

                        with LockFile(self._lock_path + '.expired', expires_after=NEVER):
                            try:
                                os.unlink(self._lock_path)
                            except OSError:
                                pass
                    except TimeoutError:
                        pass

                    # Only try this once.
                    expires = time.time() + NEVER
                else:
                    time.sleep(SLEEP_PERIOD)

        if not acquired:
            raise TimeoutError("Lock on file '{}' could not be acquired.".format(self._lock_path))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Delete the lockfile, thereby releasing the lock.
        :raises RuntimeError: When we can't delete our own lockfile for some reason.
        """

        try:
            os.unlink(self._lock_path)
        except OSError as err:
            # There isn't really anything we can do in this case.
            host, user, expiration, id = self.read_lockfile()

            if id == self._id:
                LOGGER.warning("Lockfile '{}' could not be deleted: '{}'"
                               .format(self._lock_path, err))
                raise RuntimeError("Lockfile '{}' did not clean up succesffully."
                                   .format(self._lock_path))

            elif id is None:
                LOGGER.error("Lockfile '{}' mysteriously replaced with one from {}."
                             .format(self._lock_path, (host, user)))
            else:
                LOGGER.error("Lockfile '{}' mysteriously disappeared."
                             .format(self._lock_path))

    @classmethod
    def _create_lockfile(cls, path, expires, id, group_id=None):
        """Create and fill out a lockfile at the given path.
        :param unicode path: Where the file will be created.
        :param int expires: How far in the future the lockfile expires.
        :param unicode id: The unique identifier for this lockfile.
        :returns: None
        :raises IOError: When the file cannot be written too.
        :raises OSError: When the file cannot be opened or already exists."""

        # DEV NOTE: This logic is separate so that we can create these files outside of
        # the standard mechanisms for testing purposes.

        fd = os.open(path, os.O_EXCL | os.O_CREAT | os.O_RDWR)
        expiration = time.time() + expires
        file_note = b"{},{},{},{}".format(os.uname()[1], os.getlogin(), expiration, id)
        os.write(fd, file_note)
        os.close(fd)

        if group_id is not None:
            try:
                os.chown(path, os.getuid(), group_id)
                os.chmod(path, 0774)
            except OSError as err:
                LOGGER.warning("Lockfile at '{}' could not set group permissions: {}"
                               .format(path, err))

    def read_lockfile(self):
        """Returns componenets of the lockfile content, or None for each of these values if
        there was an error..
        :returns: host, user, expiration (as a float), id
        """

        try:
            with open(self._lock_path, 'rb') as file:
                data = file.read()

            try:
                host, user, expiration, id = data.split(',')
                expiration = float(expiration)
            except ValueError:
                return None, None, None, None

        except (OSError, IOError):
            return None, None, None, None

        return host, user, expiration, id
