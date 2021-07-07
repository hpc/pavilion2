"""Manages the setup of various logging mechanisms for Pavilion."""

import logging
from logging import handlers
import socket
import sys
import traceback
from pathlib import Path

from pavilion import output
from pavilion.lockfile import LockFile
from pavilion.permissions import PermissionsManager


class LockFileRotatingFileHandler(logging.Handler):
    """A logging handler that manages cross-system, cross-process safety by
    utilizing file based locking. This will also rotate files, as per
    RotatingFileHandler.
    """

    # What to use to separate logfile lines.
    TERMINATOR = '\n'

    # For printing errors/exceptions.
    ERR_OUT = sys.stderr

    def __init__(self, file_name, max_bytes=0, backup_count=0,
                 lock_timeout=10, encoding=None):
        """Initialize the Locking File Handler. This will attempt to open
        the file and use the lockfile, just to check permissions.

        :param Union(str,Path) file_name: The path to the log file.
        :param int max_bytes: The limit of how much data can go in a single
            log file before rolling over. Zero denotes no limit.
        :param int backup_count: How many backups (logfile.1, etc) to keep.
        :param int lock_timeout: Wait this long before declaring a lock
            deadlock, and giving up.
        :param str encoding: The file encoding to use for the log file.
        """

        self.file_name = Path(file_name)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.mode = 'a'
        self.encoding = encoding
        self.lock_timeout = lock_timeout
        lockfile_path = self.file_name.parent/(self.file_name.name + '.lock')
        self.lock_file = LockFile(lockfile_path,
                                  timeout=self.lock_timeout)

        super().__init__()

    # We don't need threading based locks.
    def _do_nothing(self):
        """createLock, acquire, release, flush, and close do nothing in
        this handler implementation."""

    # We don't need thread based locking.
    createLock = _do_nothing
    acquire = _do_nothing
    release = _do_nothing
    # The log file is opened, flushed and closed for each write.
    flush = _do_nothing
    close = _do_nothing

    def emit(self, record):
        """Emit the given record, but only after acquiring a lock on the
        log's lockfile."""

        try:
            msg = self.format(record)

            with self.lock_file:
                if self._should_rollover(msg):
                    self._do_rollover()

                with self.file_name.open(self.mode) as file:
                    file.write(msg)
                    file.write(self.TERMINATOR)

        except (OSError, IOError, TimeoutError):
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        """Print any logging errors to stderr. We want to know about them."""

        try:
            self.ERR_OUT.write('--- Logging error ---\n')
            self.ERR_OUT.write('While trying to log: {}\n'.format(record.msg))
            self.ERR_OUT.write('to file: {}\n'.format(self.file_name))
            traceback.print_exc(file=self.ERR_OUT)
        except (OSError, IOError):
            pass

    def _should_rollover(self, msg):
        """Check if the message will exceed our rollover limit."""

        if 0 < self.max_bytes < self.file_name.stat().st_size + len(msg) + 1:
            return True

        return False

    def _do_rollover(self):
        """Roll over our log file. We must have a lock on the file to perform
        this."""

        if self.backup_count > 0:
            parent = self.file_name.parent

            # Move each previously rolled over log to the next higher number.
            for i in range(self.backup_count - 1, 0, -1):
                # Doing an ext
                src_fn = parent/'{}.{}'.format(self.file_name.name, i)
                dest_fn = parent/'{}.{}'.format(self.file_name.name, i + 1)
                if dest_fn.exists():
                    dest_fn.unlink()
                if src_fn.exists():
                    src_fn.rename(dest_fn)

            # Roll over the base log.
            dest_fn = parent/'{}.{}'.format(self.file_name.name, 1)
            if dest_fn.exists():
                dest_fn.unlink()
            self.file_name.rename(dest_fn)
            self.file_name.touch()
            self.file_name.chmod(0o660)


# We don't want to have to look this up every time we log.
_OLD_FACTORY = logging.getLogRecordFactory()
_HOSTNAME = socket.gethostname()


def record_factory(*fargs, **kwargs):
    """Add the hostname to all logged records."""
    record = _OLD_FACTORY(*fargs, **kwargs)
    record.hostname = _HOSTNAME
    return record


def setup_loggers(pav_cfg, verbose=False, err_out=sys.stderr):
    """Setup the loggers for the Pavilion command. This will include:

    - The general log file (as a multi-process/host safe rotating logger).
    - The result log file (also as a multi-process/host safe rotating logger).
    - The exception log.

    :param pav_cfg: The Pavilion configuration.
    :param bool verbose: When verbose, setup the root logger to print to stderr
        as well.
    :param IO[str] err_out: Where to log errors meant for the terminal. This
        exists primarily for testing.
    """

    root_logger = logging.getLogger()

    # Setup the new record factory.
    logging.setLogRecordFactory(record_factory)

    perm_man = PermissionsManager(None, pav_cfg['shared_group'],
                                  pav_cfg['umask'])

    # Put the log file in the lowest common pav config directory we can write
    # to.
    log_fn = pav_cfg.working_dir/'pav.log'
    # Set up a rotating logfile than rotates when it gets larger
    # than 1 MB.
    try:
        log_fn.touch()
    except (PermissionError, FileNotFoundError) as err:
        output.fprint("Could not write to pavilion log at '{}': {}"
                      .format(log_fn, err),
                      color=output.YELLOW,
                      file=err_out)
    else:
        file_handler = logging.FileHandler(filename=log_fn.as_posix())
        file_handler.setFormatter(logging.Formatter(pav_cfg.log_format,
                                                    style='{'))
        file_handler.setLevel(getattr(logging,
                                      pav_cfg.log_level.upper()))
        root_logger.addHandler(file_handler)

    try:
        perm_man.set_perms(log_fn)
    except OSError:
        pass

    # The root logger should pass all messages, even if the handlers
    # filter them.
    root_logger.setLevel(logging.DEBUG)

    # Setup the result logger.
    # Results will be logged to both the main log and the result log.
    try:
        pav_cfg.result_log.touch()
    except (PermissionError, FileNotFoundError) as err:
        output.fprint(
            "Could not write to result log at '{}': {}"
            .format(pav_cfg.result_log, err),
            color=output.YELLOW, file=err_out)
        return False
    try:
        perm_man.set_perms(pav_cfg.result_log)
    except OSError:
        pass

    result_logger = logging.getLogger('common_results')
    result_handler = LockFileRotatingFileHandler(
        file_name=str(pav_cfg.result_log),
        # 20 MB
        max_bytes=20 * 1024 ** 2,
        backup_count=3)
    result_handler.setFormatter(logging.Formatter("{message}", style='{'))
    result_logger.setLevel(logging.INFO)
    result_logger.addHandler(result_handler)

    # Setup the exception logger.
    # Exceptions will be logged to this directory, along with other useful info.
    exc_logger = logging.getLogger('exceptions')
    try:
        pav_cfg.exception_log.touch()
    except (PermissionError, FileNotFoundError) as err:
        output.fprint(
            "Could not write to exception log at '{}': {}"
            .format(pav_cfg.exception_log, err),
            color=output.YELLOW,
            file=err_out
        )
    else:
        exc_handler = LockFileRotatingFileHandler(
            file_name=pav_cfg.exception_log.as_posix(),
            max_bytes=20 * 1024 ** 2,
            backup_count=3)
        exc_handler.setFormatter(logging.Formatter(
            "{asctime} {message}",
            style='{',
        ))
        exc_logger.setLevel(logging.ERROR)
        exc_logger.addHandler(exc_handler)

    try:
        perm_man.set_perms(pav_cfg.exception_log)
    except OSError:
        pass

    # Setup the yapsy logger to log to terminal. We need to know immediatly
    # when yapsy encounters errors.
    yapsy_logger = logging.getLogger('yapsy')
    yapsy_handler = logging.StreamHandler(stream=err_out)
    # Color all these error messages red.
    yapsy_handler.setFormatter(
        logging.Formatter("\x1b[31m{asctime} {message}\x1b[0m",
                          style='{'))
    yapsy_logger.setLevel(logging.INFO)
    yapsy_logger.addHandler(yapsy_handler)

    # Add a stream to stderr if we're in verbose mode, or if no other handler
    # is defined.
    if verbose or not root_logger.handlers:
        verbose_handler = logging.StreamHandler(err_out)
        verbose_handler.setLevel(logging.DEBUG)
        verbose_handler.setFormatter(logging.Formatter(pav_cfg.log_format,
                                                       style='{'))
        root_logger.addHandler(result_handler)

    return True
