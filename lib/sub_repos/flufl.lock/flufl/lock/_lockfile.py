# Adapted from: flufl.lock/_lockfile.py (https://gitlab.com/warsaw/flufl.lock/-/tree/6.0)
# Copyright 2021 Barry Warsaw
# Modifications Copyright 2026 Los Alamos National Laboratory
# Licensed under the Apache License, Version 2.0
#
# Modifications:
# - Adapted to remove dependency on `psutil` and `public` packages (2026, Hank Wikle, Los Alamos National Laboratory)
# - Modified Lock class to take `Path` object instead of string (2026, Hank Wikle, Los Alamos National Laboratory)
# - Replaced custom `TimeOutError` with native Python `TimeoutError` (2026, Hank Wikle, Los Alamos National Laboratory)
#
# Original license text is included in LICENSE file.

import os
import sys
import time
import errno
import random
import socket
import logging

from contextlib import suppress
from datetime import datetime, timedelta
from enum import Enum
from logging import NullHandler
from pathlib import Path
from types import TracebackType
from typing import cast, List, Optional, Tuple, Type, Union


try:
    from typing import Literal
except ImportError:                                 # pragma: nocover
    from typing_extensions import Literal  # type: ignore


Interval = Union[timedelta, int]

# 2020-06-26(bwarsaw): Once Python 3.8 is the minimum, we could annotatey some
# of these module globals as typing.Final.


DEFAULT_LOCK_LIFETIME = timedelta(seconds=15)
# Allowable a bit of clock skew.
CLOCK_SLOP = timedelta(seconds=10)
MAXINT = sys.maxsize

# Details separator; also used in calculating the claim file path.  Lock files
# should not include this character.  We do it like this so flake8 won't
# complain about SEP.
SEP = '^' if sys.platform == 'win32' else '|'

# LP: #977999 - catch both ENOENT and ESTALE.  The latter is what an NFS
# server should return, but some Linux versions return ENOENT.
ERRORS = (errno.ENOENT, errno.ESTALE)

log = logging.getLogger('flufl.lock')

# Install a null handler to avoid warnings when applications don't set their
# own flufl.lock logger.  See http://docs.python.org/library/logging.html
logging.getLogger('flufl.lock').addHandler(NullHandler())


class LockError(Exception):
    """Base class for all exceptions in this module."""


class AlreadyLockedError(LockError):
    """An attempt is made to lock an already locked object."""


class NotLockedError(LockError):
    """An attempt is made to unlock an object that isn't locked."""


class LockState(Enum):
    """Infer the state of the lock.

    There are cases in which it is impossible to infer the state of the lock,
    due to the distributed nature of the locking mechanism and environment.
    However it is possible to provide some insights into the state of the
    lock.  Note that the policy on what to do with this information is left
    entirely to the user of the library.
    """

    #: There is no lock file so the lock is unlocked.
    unlocked = 1
    #: We own the lock and it is fresh.
    ours = 2
    #: We own the lock but it has expired.  Another process trying
    #: to acquire the lock will break it.
    ours_expired = 3
    #: We don't own the lock; the hostname in the details matches our
    #: hostname and there is no pid running that matches pid.  Therefore,
    #: the lock is stale.
    stale = 4
    #: Some other process owns the lock (probably) but it has expired.  Another
    #: process trying to acquire the lock will break it.
    theirs_expired = 5
    #: We don't own the lock; either our hostname does not match the
    #: details, or there is a process (that's not us) with a matching pid.
    #: The state of the lock is therefore unknown.
    unknown = 6


def _interval_to_datetime(
    timeout: Optional[Interval] = None,
) -> Optional[datetime]:
    if timeout is None:
        return None
    if isinstance(timeout, int):
        timeout = timedelta(seconds=timeout)
    return datetime.now() + timeout


def pid_exists(pid: int) -> bool:
    """Check whether pid exists in the current process table."""

    if pid <= 0:
        return False
    try:
        # Signal 0 doesn't kill the process, but raises an OSError if the pid doesn't exist.
        os.kill(pid, 0)
    except OSError as e:
        if e.errno == errno.ESRCH:   # No such process
            return False
        elif e.errno == errno.EPERM: # Process exists but no permission
            return True
        else:
            raise
    else:
        return True


class Lock:
    """Portable, NFS-safe file locking with timeouts for POSIX systems.

    This class implements an NFS-safe file-based locking algorithm
    influenced by the GNU/Linux open(2) manpage, under the description
    of the O_EXCL option:

        [...] O_EXCL is broken on NFS file systems, programs which rely on it
        for performing locking tasks will contain a race condition.  The
        solution for performing atomic file locking using a lockfile is to
        create a unique file on the same fs (e.g., incorporating hostname and
        pid), use link(2) to make a link to the lockfile.  If link() returns
        0, the lock is successful.  Otherwise, use stat(2) on the unique file
        to check if its link count has increased to 2, in which case the lock
        is also successful.

    The assumption made here is that there will be no *outside interference*,
    e.g. no agent external to this code will ever link() to the specific lock
    files used.

    The user specifies a *lock file* in the constructor of this class.  This
    is whatever file system path the user wants to coordinate locks on.  When
    a process attempts to acquire a lock, it first writes a *claim file* which
    contains unique details about the lock being acquired (e.g. the lock file
    name, the hostname, the pid of the process, and a random integer).  Then
    it attempts to create a hard link from the claim file to the lock file.
    If no other process has the lock, this hard link succeeds and the process
    accquires the lock.  If another process already has the lock, the hard
    link will fail and the lock will not be acquired.  What happens in this
    and other error conditions are described in the more detailed
    documentation.

    Lock objects support lock-breaking so that you can't wedge a process
    forever.  This is especially helpful in a web environment, but may
    not be appropriate for all applications.

    Locks have a ``lifetime``, which is the maximum length of time the
    process expects to retain the lock.  It is important to pick a good
    number here because other processes will not break an existing lock
    until the expected lifetime has expired.  Too long and other
    processes will hang; too short and you'll end up trampling on
    existing process locks -- and possibly corrupting data.  However
    locks also support extending a lock's lifetime.  In a distributed
    (NFS) environment, you also need to make sure that your clocks are
    properly synchronized.

    Each process laying claim to this resource lock will create their own
    temporary lock file based on the path specified.  An optional lifetime
    is the length of time that the process expects to hold the lock.

    :param lockfile: The full path to the lock file.
    :param lifetime: The expected maximum lifetime of the lock, as a
        timedelta or integer number of seconds, relative to now.  Defaults
        to 15 seconds.
    :param separator: The separator character to use in the lock file's
        file name.  Defaults to the vertical bar (`|`) on POSIX systems
        and caret (`^`) on Windows.
    :param default_timeout: Default timeout for approximately how long the lock
        acquisition attempt should be made. The value given in the `.lock()`
        call always overrides this.
    """

    def __init__(
        self,
        lockfile: Path,
        lifetime: Optional[Interval] = None,
        separator: str = SEP,
        default_timeout: Optional[Interval] = None,
    ):
        """Create the resource lock using the given file name and lifetime."""
        # The hostname has to be defined before we call _set_claimfile().
        self._hostname = socket.getfqdn()
        if lifetime is None:
            lifetime = DEFAULT_LOCK_LIFETIME
        self._default_timeout = default_timeout
        self._lockfile = lockfile
        # https://github.com/python/mypy/issues/3004
        self.lifetime = lifetime                    # type: ignore
        # The separator must be set before we claim the lock.
        self._separator = separator
        self._claimfile: Path
        self._set_claimfile()
        # For extending the set of NFS errnos that are retried in _read().
        self._retry_errnos: List[int] = []

    def __repr__(self) -> str:
        return '<%s %s [%s: %s] pid=%s at %#xx>' % (
            self.__class__.__name__,
            self._lockfile,
            ('locked' if self._is_locked_no_refresh() else 'unlocked'),
            self._lifetime,
            os.getpid(),
            id(self),
        )

    @property
    def hostname(self) -> str:
        """The current machine's host name.

        :return: The current machine's hostname, as used in the `.details`
            property.
        """
        return self._hostname

    @property
    def details(self) -> Tuple[str, int, str]:
        """Details as read from the lock file.

        :return: A 3-tuple of hostname, process id, lock file name.
        :raises NotLockedError: if the lock is not acquired.
        """
        try:
            with open(self._lockfile) as fp:
                filename = fp.read().strip()
        except OSError as error:
            if error.errno in ERRORS:
                raise NotLockedError('Details are unavailable') from error
            raise
        # Rearrange for signature.
        try:
            lockfile, hostname, pid, random_ignored = filename.split(
                self._separator
            )
        except ValueError as error:
            raise NotLockedError('Details are unavailable') from error
        return hostname, int(pid), lockfile

    @property
    def state(self) -> LockState:
        """Infer the state of the lock."""
        try:
            with open(self._lockfile) as fp:
                filename = fp.read().strip()
        except FileNotFoundError:
            return LockState.unlocked
        try:
            lockfile, hostname, pid_str, random_ignored = filename.split(
                self._separator
            )
            pid = int(pid_str)
        except (ValueError, TypeError):
            # The contents of the lock file is corrupt, so we can't know
            # anything about the state of the lock.
            return LockState.unknown
        if hostname != self._hostname:
            return LockState.unknown
        if pid == os.getpid():
            expired = self.expiration < datetime.now()
            return LockState.ours_expired if expired else LockState.ours
        if pid_exists(pid):
            expired = self.expiration < datetime.now()
            return LockState.theirs_expired if expired else LockState.unknown
        return LockState.stale

    @property
    def lifetime(self) -> timedelta:
        """The current lock life time."""
        return self._lifetime

    @lifetime.setter
    def lifetime(self, lifetime: Interval) -> None:
        if isinstance(lifetime, timedelta):
            self._lifetime = lifetime
        else:
            self._lifetime = timedelta(seconds=lifetime)

    def refresh(
        self,
        lifetime: Optional[Interval] = None,
        *,
        unconditionally: bool = False
    ) -> None:
        """Refreshes the lifetime of a locked file.

        Use this if you realize that you need to keep a resource locked longer
        than you thought.

        :param lifetime: If given, this sets the lock's new lifetime.  It
            represents the number of seconds into the future that the
            lock's lifetime will expire, relative to now, or whenever it is
            refreshed, either explicitly or implicitly.  If not given, the
            original lifetime interval is used.
        :param unconditionally: When False (the default), a ``NotLockedError``
            is raised if an unlocked lock is refreshed.
        :raises NotLockedError: if the lock is not set, unless optional
            ``unconditionally`` flag is set to True.
        """
        if lifetime is not None:
            # https://github.com/python/mypy/issues/3004
            self.lifetime = lifetime                # type: ignore
        # Do we have the lock?  As a side effect, this refreshes the lock!
        if not self.is_locked and not unconditionally:
            raise NotLockedError('{}: {}'.format(repr(self), self._read()))

    def lock(self, timeout: Optional[Interval] = None) -> None:
        """Acquire the lock.

        This blocks until the lock is acquired unless optional timeout is not
        None, in which case a ``TimeoutError`` is raised when the timeout
        expires without lock acquisition.

        :param timeout: Approximately how long the lock acquisition attempt
            should be made.  None (the default) means keep trying forever.
        :raises AlreadyLockedError: if the lock is already acquired.
        :raises TimeoutError: if ``timeout`` is not None and the indicated
            time interval expires without a lock acquisition.
        """
        timeout_time = _interval_to_datetime(
            self._default_timeout if timeout is None else timeout
        )
        # Make sure the claim file exists, and that its contents are current.
        self._write()
        # XXX This next call can fail with an EPERM.  I have no idea why, but
        # I'm nervous about ignoring it.  It seems to be a very rare
        # occurrence, only happens from cron, and has only(?) been observed on
        # Solaris 2.6.
        self._touch()
        log.debug('laying claim: {}'.format(self._lockfile))
        # For quieting the logging output.
        loopcount = -1
        while True:
            loopcount += 1
            # Create the hard link from the claim file to the lock file and
            # test for a hard count of exactly 2 links.
            try:
                os.link(self._claimfile, self._lockfile)
                # If we got here, we know we got the lock, and never
                # had it before, so we're done.  Just touch it again for the
                # fun of it.
                log.debug('got the lock: {}'.format(self._lockfile))
                self._touch()
                break
            except OSError as error:
                # The link failed for some reason, possibly because someone
                # else already has the lock (i.e. we got an EEXIST), or for
                # some other bizarre reason.
                if error.errno in ERRORS:
                    # XXX in some Linux environments, it is possible to get an
                    # ENOENT, which is truly strange, because this means that
                    # self._claimfile didn't exist at the time of the
                    # os.link(), but self._write() is supposed to guarantee
                    # that this happens!  I don't honestly know why this
                    # happens -- possibly due to weird caching file systems?
                    # -- but for now we just say we didn't acquire the lock
                    # and try again next time.
                    pass
                elif error.errno != errno.EEXIST:
                    # Something very bizarre happened.  Clean up our state and
                    # pass the error on up.
                    log.exception('unexpected link')
                    os.unlink(self._claimfile)
                    raise
                elif self._linkcount != 2:
                    # Somebody's messin' with us!  Log this, and try again
                    # later.  XXX should we raise an exception?
                    log.error(
                        'unexpected linkcount: {0:d}'.format(self._linkcount)
                    )
                elif self._read() == str(self._claimfile):
                    # It was us that already had the link.
                    log.debug('already locked: {}'.format(self._lockfile))
                    raise AlreadyLockedError('We already had the lock')
                # Otherwise, someone else has the lock
                pass
            # We did not acquire the lock, because someone else already has
            # it.  Have we timed out in our quest for the lock?
            if timeout_time is not None and timeout_time < datetime.now():
                os.unlink(self._claimfile)
                log.error('timed out')
                raise TimeoutError('Could not acquire the lock')
            # Okay, we haven't timed out, but we didn't get the lock.  Let's
            # find out if the lock lifetime has expired.  Cache the release
            # time to avoid race conditions.  (LP: #827052)
            release_time = self._releasetime
            if release_time != -1:
                now = datetime.now()
                future = cast(datetime, release_time) + CLOCK_SLOP
                if now > future:
                    # Yes, so break the lock.
                    self._break()
                log.error('lifetime has expired, breaking')
            # Okay, someone else has the lock, our claim hasn't timed out yet,
            # and the expected lock lifetime hasn't expired yet either.  So
            # let's wait a while for the owner of the lock to give it up.
            elif not loopcount % 100:
                log.debug('waiting for claim: {}'.format(self._lockfile))
            self._sleep()

    # 2020-06-27(bwarsaw): `unconditionally` should really be a keyword-only
    # argument, but those didn't exist when this library was originally
    # written, and changing that now would be a needless backward incompatible
    # API break.
    def unlock(self, *, unconditionally: bool = False) -> None:
        """Release the lock.

        :param unconditionally: When False (the default), a ``NotLockedError``
            is raised if this is called on an unlocked lock.
        :raises NotLockedError: if we don't own the lock, either because of
            unbalanced unlock calls, or because the lock was stolen out from
            under us, unless optional ``unconditionally`` is True.
        """
        is_locked = self.is_locked
        if not is_locked and not unconditionally:
            raise NotLockedError('Already unlocked')
        # If we owned the lock, remove the lockfile, relinquishing the lock.
        if is_locked:
            try:
                os.unlink(self._lockfile)
            except OSError as error:
                if error.errno not in ERRORS:
                    raise
        # Remove our claim file.
        try:
            os.unlink(self._claimfile)
        except OSError as error:
            if error.errno not in ERRORS:
                raise
        log.debug('unlocked: {}'.format(self._lockfile))

    def _is_locked_no_refresh(self) -> bool:
        """Don't refresh the lock, just return the status."""
        # XXX Can the link count ever be > 2?
        if self._linkcount != 2:
            return False
        return self._read() == str(self._claimfile)

    @property
    def is_locked(self) -> bool:
        """True if we own the lock, False if we do not.

        Checking the status of the lock resets the lock's lifetime, which
        helps avoid race conditions during the lock status test.
        """
        # Discourage breaking the lock for a while.
        try:
            self._touch()
        except PermissionError:
            # We can't touch the file because we're not the owner.  I don't see
            # how we can own the lock if we're not the owner.
            log.error('No permission to refresh the log')
            return False
        return self._is_locked_no_refresh()

    def __enter__(self) -> 'Lock':
        self.lock()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> Literal[False]:
        self.unlock()
        # Don't suppress any exception that might have occurred.
        return False

    def _set_claimfile(self) -> None:
        """Set the _claimfile private variable."""
        # Calculate a hard link file name that will be used to lay claim to
        # the lock.  We need to watch out for two Lock objects in the same
        # process pointing to the same lock file.  Without this, if you lock
        # lf1 and do not lock lf2, lf2.locked() will still return True.
        self._claimfile = Path(self._separator.join(
            (
                str(self._lockfile),
                self.hostname,
                str(os.getpid()),
                str(random.randint(0, MAXINT)),
            )
        ))

    def _write(self) -> None:
        """Write our claim file's name to the claim file."""
        # Make sure it's group writable.
        with open(self._claimfile, 'w') as fp:
            fp.write(str(self._claimfile))

    @property
    def retry_errnos(self) -> List[int]:
        """The set of errno values that cause a read retry."""
        return self._retry_errnos[:]

    @retry_errnos.setter
    def retry_errnos(self, errnos: List[int]) -> None:
        self._retry_errnos = []
        self._retry_errnos.extend(errnos)

    @retry_errnos.deleter
    def retry_errnos(self) -> None:
        self._retry_errnos = []

    @property
    def expiration(self) -> datetime:
        """The lock's expiration time, regardless of ownership."""
        return datetime.fromtimestamp(os.stat(self._lockfile).st_mtime)

    @property
    def lockfile(self) -> str:
        """Return the lock file name."""
        return self._lockfile

    def _read(self) -> Optional[str]:
        """Read the contents of our lock file.

        :return: The contents of the lock file or None if the lock file does
            not exist.
        """
        while True:
            try:
                with open(self._lockfile) as fp:
                    return fp.read()
            except EnvironmentError as error:
                if error.errno in self._retry_errnos:
                    self._sleep()
                elif error.errno not in ERRORS:
                    raise
                else:
                    return None

    def _touch(self, filename: Optional[str] = None) -> None:
        """Touch the claim file into the future.

        :param filename: If given, the file to touch, otherwise our claim file
            is touched.
        """
        expiration_date = datetime.now() + self._lifetime
        t = time.mktime(expiration_date.timetuple())
        try:
            # XXX We probably don't need to modify atime, but this is easier.
            os.utime(filename or self._claimfile, (t, t))
        except OSError as error:
            if error.errno not in ERRORS:
                raise

    @property
    def _releasetime(self) -> Union[int, datetime]:
        """The time when the lock should be released.

        :return: The mtime of the file, which is when the lock should be
            released, or -1 if the lockfile doesn't exist.
        """
        try:
            return self.expiration
        except OSError as error:
            if error.errno in ERRORS:
                return -1
            raise

    @property
    def _linkcount(self) -> int:
        """The number of hard links to the lock file.

        :return: the number of hard links to the lock file, or -1 if the lock
            file doesn't exist.
        """
        try:
            return os.stat(self._lockfile).st_nlink
        except OSError as error:
            if error.errno in ERRORS:
                return -1
            raise

    def _break(self) -> None:
        """Break the lock."""
        # Try to read from the lock file.  All we care about is that its
        # contents have the details expected of any lock file.  If not, then
        # this probably isn't a lock that needs breaking, it's a Lock with a
        # lock file pointing to an existing, unrelated file.  Refuse to break
        # that lock.  All we really need to do is to log and return.  If a
        # timeout was given, eventually the .lock() call will timeout.
        # However if no timeout was given, the .lock() will block forever.
        try:
            self.details
        except NotLockedError:
            log.error(
                "lockfile exists but isn't safe to break: {}".format(
                    self._lockfile
                )
            )
            return
        # Touch the lock file.  This reduces but does not eliminate the
        # chance for a race condition during breaking.  Two processes could
        # both pass the test for lock expiry in lock() before one of them gets
        # to touch the lock file.  This shouldn't be too bad because all
        # they'll do in that function is delete the lock files, not claim the
        # lock, and we can be defensive for ENOENTs here.
        #
        # Touching the lock could fail if the process breaking the lock and
        # the process that claimed the lock have different owners.  Don't do
        # that.
        with suppress(PermissionError):
            self._touch(self._lockfile)
        # Get the name of the old winner's claim file.
        winner = self._read()
        # Remove the global lockfile, which actually breaks the lock.
        try:
            os.unlink(self._lockfile)
        except OSError as error:                    # pragma: nocover
            if error.errno not in ERRORS:
                raise
        # Try to remove the old winner's claim file, since we're assuming the
        # winner process has hung or died.  Don't worry too much if we can't
        # unlink their claim file -- this doesn't wreck the locking algorithm,
        # but will leave claim file turds laying around, a minor inconvenience.
        try:
            if winner:                              # pragma: nobranch
                os.unlink(winner)
        except OSError as error:
            if error.errno not in ERRORS:           # pragma: nocover
                raise

    def _sleep(self) -> None:
        """Snooze for a random amount of time."""
        interval = random.random() * 2.0 + 0.01
        time.sleep(interval)
