from __future__ import division, unicode_literals, print_function

import grp
import logging
import os
import time
import uuid

LOGGER = logging.getLogger('pav.' + __name__)


# Expires after a silly long time.
NEVER = 10**10


class TimeoutError(RuntimeError):
    """Error raised when the lockfile times out."""
    pass


class LockFile(object):
    """An NFS friendly way to create a lock file. Locks contain information on what host and user
    created the lock, and have a built in expiration date. To be used in a 'with' context.
    :cvar DEFAULT_EXPIRE: How long it takes for a lock to expire."""

    # Time till file is considered stale, in seconds. (5 minute default)
    DEFAULT_EXPIRE = 60 * 60 * 5

    # How long to sleep between lock attempts.
    # This shouldn't be any less than 0.01 or so on a regular filesystem. 0.2 is pretty reasonable
    # for an nfs filesystem and sporadically used locks.
    SLEEP_PERIOD = 0.2

    # Default lock permissions
    LOCK_PERMS = 0774

    def __init__(self, lockfile_path, group=None, timeout=None, expires_after=DEFAULT_EXPIRE):
        """Initialize the lock file. The resulting class can be reused multiple times.
        :param unicode lockfile_path: The path to the lockfile. Should probably start with a '.',
        and end with '.lock', but that's up to the user.
        :param unicode group: The name of the group to set lockfiles to. If this is given,
        :param timeout: When to quit trying to acquire the lock in seconds. None (default) denotes
        non-blocking mode.
        :param expires_after: When to consider the lock dead, and overwritable (in seconds). The
        NEVER module variable is provided as easily named long time. (10^10 secs, 317 years)
        """

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
                    time.sleep(self.SLEEP_PERIOD)

        if not acquired:
            raise TimeoutError("Lock on file '{}' could not be acquired.".format(self._lock_path))

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Delete the lockfile, thereby releasing the lock.
        :raises RuntimeError: When we can't delete our own lockfile for some reason.
        """

        # There isn't really anything we can do in this case.
        host, user, expiration, lock_id = self.read_lockfile()

        if lock_id is not None and lock_id != self._id:
            LOGGER.error("Lockfile '{}' mysteriously replaced with one from {}."
                         .format(self._lock_path, (host, user)))
        else:
            try:
                os.unlink(self._lock_path)
            except OSError as err:
                # There isn't really anything we can do in this case.
                host, user, expiration, lock_id = self.read_lockfile()

                if lock_id == self._id:
                    LOGGER.warning("Lockfile '{}' could not be deleted: '{}'"
                                   .format(self._lock_path, err))
                else:
                    LOGGER.error("Lockfile '{}' mysteriously disappeared."
                                 .format(self._lock_path))

    @classmethod
    def _create_lockfile(cls, path, expires, lock_id, group_id=None):
        """Create and fill out a lockfile at the given path.
        :param unicode path: Where the file will be created.
        :param int expires: How far in the future the lockfile expires.
        :param unicode lock_id: The unique identifier for this lockfile.
        :returns: None
        :raises IOError: When the file cannot be written too.
        :raises OSError: When the file cannot be opened or already exists."""

        # DEV NOTE: This logic is separate so that we can create these files outside of
        # the standard mechanisms for testing purposes.

        fd = os.open(path, os.O_EXCL | os.O_CREAT | os.O_RDWR)
        expiration = time.time() + expires
        file_note = b"{},{},{},{}".format(os.uname()[1], os.getlogin(), expiration, lock_id)
        os.write(fd, file_note)
        os.close(fd)

        try:
            os.chmod(path, cls.LOCK_PERMS)
        except OSError as err:
            LOGGER.warning("Lockfile at '{}' could not set permissions: {}"
                           .format(path, err))

        if group_id is not None:
            try:
                os.chown(path, os.getuid(), group_id)
            except OSError as err:
                LOGGER.warning("Lockfile at '{}' could not set group: {}"
                               .format(path, err))

    def read_lockfile(self):
        """Returns componenets of the lockfile content, or None for each of these values if
        there was an error..
        :returns: host, user, expiration (as a float), id
        """

        try:
            with open(self._lock_path, 'rb') as lock_file:
                data = lock_file.read()

            try:
                host, user, expiration, lock_id = data.split(',')
                expiration = float(expiration)
            except ValueError:
                LOGGER.warning("Invalid format in lockfile '{}': {}".format(self._lock_path, data))
                return None, None, None, None

        except (OSError, IOError):
            return None, None, None, None

        return host, user, expiration, lock_id
