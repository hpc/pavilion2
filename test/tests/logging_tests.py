"""Test Pavilion logging setup."""

import io
import logging
import uuid
import json
from pathlib import Path
import threading

from pavilion.log_setup import LockFileRotatingFileHandler, setup_loggers
from pavilion.unittest import PavTestCase


class LoggingTests(PavTestCase):
    """Test Pavilion logging mechanisms."""

    def test_setup_logger(self):

        err_out = io.StringIO()

        setup_loggers(self.pav_cfg, err_out=err_out)

        # Log through each of the logging mechanisms.

        # Check the result logger
        result_logger = logging.getLogger('common_results')
        result_msg = json.dumps({
            "name": str(uuid.uuid4()),
        })
        result_logger.error(result_msg)
        # Make sure our message got logged.
        result_log_data = self.pav_cfg.result_log.open().read()
        self.assertIn(result_msg + '\n', result_log_data)

        # Check that yapsy errors go to stderr (or the stream we replaced
        # stderr with).
        yapsy_logger = logging.getLogger('yapsy')
        yapsy_msg = str(uuid.uuid4())
        yapsy_logger.error("Testing logging through yapsy. %s", yapsy_msg)
        self.assertIn(yapsy_msg, err_out.getvalue())

        # Check that exceptions get logged too.
        exc_logger = logging.getLogger('exceptions')
        exc_msg = str(uuid.uuid4())
        exc_logger.error(exc_msg)
        exc_log_data = self.pav_cfg.exception_log.open().read()
        self.assertIn(exc_msg, exc_log_data)

        # This should log through the 'root' logger.
        my_logger = logging.getLogger(__file__)
        root_msg = str(uuid.uuid4())
        my_logger.error(root_msg)
        root_log_data = (self.pav_cfg.working_dir/'pav.log').open().read()
        # All data goes to the root log as well.
        self.assertIn(result_msg, root_log_data)
        self.assertIn(yapsy_msg, root_log_data)
        self.assertIn(exc_msg, root_log_data)
        self.assertIn(root_msg, root_log_data)

    @staticmethod
    def _make_record(msg):
        """Make a test record for logging.
        :param str msg: The message to log.
        :returns: (record, ident_str)
        """

        ident = str(uuid.uuid4())

        rec = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            msg=msg + ident,
            pathname=__file__,
            lineno=67,
            exc_info=None,
            args={}
        )

        return rec, ident

    def test_lockfile_handler(self):
        """Exercise components of the LockFileRotatingFileHandler.
        This can't check if this actually works across processes/hosts. We
        have to trust the Pavilion LockFile class for that."""

        logfile_path = self.pav_cfg.working_dir/'lockfile_handler_test'

        if logfile_path.exists():
            logfile_path.unlink()

        handler = LockFileRotatingFileHandler(
            file_name=logfile_path,
            max_bytes=1024,
            backup_count=2,
            lock_timeout=1
        )

        rec, ident = self._make_record("My first record")

        handler.ERR_OUT = io.StringIO()

        handler.handle(rec)
        # Make sure a single log entry actually gets logged.
        self.assertIn(ident, logfile_path.open().read())

        # Make sure our file rolls over when it exceeds the limit, and
        # that it makes the proper number of backups.
        for i in range(100):
            rec, ident = self._make_record(str(i)*100)
            handler.handle(rec)
            self.assertIn(ident, logfile_path.open().read())

        # This should have been more than enough to create several backups,
        # but the limit is two.
        backup1 = logfile_path.with_suffix(logfile_path.suffix + '.1')
        backup2 = logfile_path.with_suffix(logfile_path.suffix + '.2')
        backup3 = logfile_path.with_suffix(logfile_path.suffix + '.3')
        self.assertTrue(backup1.exists())
        self.assertTrue(backup2.exists())
        self.assertFalse(backup3.exists())

        # Make sure we haven't seen any errors
        self.assertEqual(handler.ERR_OUT.getvalue(), '')

        # If the lock times out, this should catch the exception and print
        # the error.
        with handler.lock_file:
            rec, ident = self._make_record('timeout')
            handler.handle(rec)

        self.assertIn(ident, handler.ERR_OUT.getvalue())
        self.assertNotIn(ident, logfile_path.open().read())
