"""Tests for timing module functionality."""

import math
import os
import tempfile
import time
from pathlib import Path

from pavilion import unittest
from pavilion.timing import AbsoluteDeadlineTimeout


class AbsoluteDeadlineTimeoutTests(unittest.PavTestCase):
    """Test the AbsoluteDeadlineTimeout class for NFS-safe timeout checking."""

    def test_basic_timeout_detection(self):
        """Test that timeout is correctly detected when deadline passes."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'test')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file, 1.0)
            
            # Initially should have remaining time
            remaining = timeout_strategy.remaining_time()
            self.assertGreater(remaining, 0)
            self.assertLessEqual(remaining, 1.0)
            
            # After timeout period, should be negative
            time.sleep(1.5)
            remaining = timeout_strategy.remaining_time()
            self.assertLess(remaining, 0)
        finally:
            test_file.unlink()

    def test_file_modification_extends_deadline(self):
        """Test that modifying the file extends the deadline."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'initial')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file, 2.0)
            
            # Wait 1 second
            time.sleep(1.0)
            
            # Modify file (simulating process writing output)
            with open(test_file, 'a') as f:
                f.write('more data')
            
            # Check remaining time - should be extended
            remaining = timeout_strategy.remaining_time()
            self.assertGreater(remaining, 1.5,
                             "Deadline should be extended after file modification")
        finally:
            test_file.unlink()

    def test_stale_mtime_preserves_deadline(self):
        """Test NFS-safe behavior: stale mtime doesn't move deadline backward."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'test')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file, 5.0)
            initial_deadline = timeout_strategy.deadline
            
            # Simulate stale cached mtime by setting file mtime to the past
            os.utime(test_file, (time.time() - 100, time.time() - 100))
            
            # Check remaining time
            remaining = timeout_strategy.remaining_time()
            new_deadline = timeout_strategy.deadline
            
            # Deadline should not move backward
            self.assertEqual(new_deadline, initial_deadline,
                           "Deadline should not move backward with stale mtime")
            self.assertGreater(remaining, 4.5,
                             "Remaining time should still be ~5s")
        finally:
            test_file.unlink()

    def test_oserror_preserves_deadline(self):
        """Test that OSError (e.g., missing file) preserves the deadline."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'test')

        timeout_strategy = AbsoluteDeadlineTimeout(test_file, 5.0)
        initial_deadline = timeout_strategy.deadline
        
        # Remove file to cause OSError
        test_file.unlink()
        
        # Check remaining time - should not crash
        remaining = timeout_strategy.remaining_time()
        
        # Deadline should be unchanged
        self.assertEqual(timeout_strategy.deadline, initial_deadline,
                       "Deadline should be unchanged after OSError")
        self.assertGreater(remaining, 4.5,
                         "Remaining time should still be ~5s")

    def test_none_timeout_returns_infinity(self):
        """Test that timeout_period=None returns infinity."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'test')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file, None)
            
            # Deadline should be infinity
            self.assertEqual(timeout_strategy.deadline, math.inf,
                           "Deadline should be infinity for None timeout")
            
            # Remaining time should be infinity
            remaining = timeout_strategy.remaining_time()
            self.assertEqual(remaining, math.inf,
                           "Remaining time should be infinity for None timeout")
        finally:
            test_file.unlink()

    def test_pathlike_string_path(self):
        """Test that string paths work (Pathlike type)."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file_str = f.name  # String, not Path
            f.write(b'test')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file_str, 5.0)
            
            # Should accept string path
            remaining = timeout_strategy.remaining_time()
            self.assertGreater(remaining, 4.5,
                             "String path should work")
        finally:
            Path(test_file_str).unlink()

    def test_multiple_checks_update_deadline(self):
        """Test that multiple checks correctly update the deadline."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'initial')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file, 3.0)
            
            # First check
            remaining1 = timeout_strategy.remaining_time()
            self.assertGreater(remaining1, 2.9)
            
            # Wait and modify file
            time.sleep(1.0)
            with open(test_file, 'a') as f:
                f.write('update')
            
            # Second check - deadline should extend
            remaining2 = timeout_strategy.remaining_time()
            self.assertGreater(remaining2, 2.5,
                             "Deadline should extend on file modification")
            
            # Third check without modification - remaining decreases
            time.sleep(0.5)
            remaining3 = timeout_strategy.remaining_time()
            self.assertLess(remaining3, remaining2,
                          "Remaining time should decrease without file modification")
        finally:
            test_file.unlink()

    def test_zero_timeout_period(self):
        """Test behavior with zero timeout period."""
        
        with tempfile.NamedTemporaryFile(delete=False) as f:
            test_file = Path(f.name)
            f.write(b'test')

        try:
            timeout_strategy = AbsoluteDeadlineTimeout(test_file, 0.0)
            
            # Should immediately be timed out (or very close)
            remaining = timeout_strategy.remaining_time()
            self.assertLessEqual(remaining, 0.1,
                               "Zero timeout should be immediately exceeded")
        finally:
            test_file.unlink()
