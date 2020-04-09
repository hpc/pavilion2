"""Manages the setup of various logging mechanisms for Pavilion."""

import logging
import socket
import sys
import traceback
from pathlib import Path

from pavilion import output
from pavilion.lockfile import LockFile


class LockFileRotatingFileHandler(logging.Handler):
    """A logging handler that manages cross-system, cross-process safety by
    utilizing file based locking. This will also rotate files, as per
    RotatingFileHandler.
    """

    TERMINATOR = '\n'

    def __init__(self, file_name, max_bytes=0, backup_count=0,
                 lock_timeout=10, encoding=None):
        """Initialize the Locking File Handler. This will attempt to open
        the file and use the lockfile, just to check permissions.

        :param lock_timeout: How long to wait before giving up and writing
        anyway.
        """

        super().__init__()

        self.file_name = Path(file_name)
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.mode = 'a'
        self.encoding = encoding
        self.lock_timeout = lock_timeout
        self.lock_file = LockFile(Path(self.file_name.name + '.lock'),
                                  timeout=self.lock_timeout)

        # Test acquire the lock file and test open the file.
        try:
            self.acquire()
            with self.file_name.open(self.mode, encoding=self.encoding):
                pass
        finally:
            self.release()

    def createLock(self):
        """Create the lock file. In this case we always have a lock."""
        # We're not going to be using the standard locks.

        raise NotImplementedError("We do this in the __init__.")

    def acquire(self):
        """Acquire the lock. Unlike with the base class, this is not
        idempotent, so we need to be careful."""

        self.lock_file.lock()

    def release(self):
        """Release the lock."""

        self.lock_file.unlock()

    def flush(self):
        """The stream is always flushed after every write, so do nothing."""

        pass

    def close(self):
        """Our close method does nothing, as we open and close the file each
        time we need to write."""

        pass

    def emit(self, record):
        """Emit the given record.
        We must first acquire a lock on the given file before we can attempt
        any actions on the file itself."""

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
            sys.stderr.write('--- Logging error ---')
            traceback.print_exc(file=sys.stderr)
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
            # Move each previously rolled over log to the next higher number.
            for i in range(self.backup_count - 1, 0, -1):
                src_fn = Path('{}.{}'.format(self.file_name.name, i))
                dest_fn = Path('{}.{}'.format(self.file_name.name, i + 1))

                if dest_fn.exists():
                    dest_fn.unlink()
                src_fn.rename(dest_fn)

            # Roll over the base log.
            dest_fn = Path('{}.{}'.format(self.file_name.name, 1))
            if dest_fn.exists():
                dest_fn.unlink()
            self.file_name.rename(dest_fn)


# We don't want to have to look this up every time we log.
_old_factory = logging.getLogRecordFactory()
_hostname = socket.gethostname()


def record_factory(*fargs, **kwargs):
    """Add the hostname to all logged records."""
    record = _old_factory(*fargs, **kwargs)
    record.hostname = _hostname
    return record


def setup_loggers(pav_cfg, verbose):
    """Setup the loggers for the Pavilion command. This will include:

    - The general log file (as a multi-process/host safe rotating logger).
    - The result log file (also as a multi-process/host safe rotating logger).
    - The exception log.

    :param pav_cfg: The Pavilion configuration.
    :param bool verbose: When verbose, setup the root logger to print to stderr
        as well.
    """

    root_logger = logging.getLogger()

    # Setup the new record factory.
    logging.setLogRecordFactory(record_factory)

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
                      file=sys.stderr,
                      )
    else:
        file_handler = LockFileRotatingFileHandler(
            file_name=log_fn,
            max_bytes=1024 ** 2,
            backup_count=3)
        file_handler.setFormatter(logging.Formatter(pav_cfg.log_format,
                                                    style='{'))
        file_handler.setLevel(getattr(logging,
                                      pav_cfg.log_level.upper()))
        root_logger.addHandler(file_handler)

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
            color=output.YELLOW,
            file=sys.stderr
        )
        sys.exit(1)

    result_logger = logging.getLogger('results')
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
            file=sys.stderr
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

    # Setup the yapsy logger to log to terminal. We need to know immediatly
    # when yapsy encounters errors.
    yapsy_logger = logging.getLogger('yapsy')
    yapsy_handler = logging.StreamHandler(stream=sys.stderr)
    # Color all these error messages red.
    yapsy_handler.setFormatter(
        logging.Formatter("\x1b[31m{asctime} {message}\x1b[0m",
                          style='{'))
    yapsy_logger.setLevel(logging.INFO)
    yapsy_logger.addHandler(yapsy_handler)

    # Add a stream to stderr if we're in verbose mode, or if no other handler
    # is defined.
    if verbose or not root_logger.handlers:
        verbose_handler = logging.StreamHandler(sys.stderr)
        verbose_handler.setLevel(logging.DEBUG)
        verbose_handler.setFormatter(logging.Formatter(pav_cfg.log_format,
                                                       style='{'))
        root_logger.addHandler(result_handler)
