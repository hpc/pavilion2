"""Tests for various utils functions."""

import os
import tempfile
from pathlib import Path

from pavilion import unittest
from pavilion import utils


class UtilsTests(unittest.PavTestCase):

    def test_relative_to(self):
        """Check relative path calculations."""

        # base, target, answer
        tests = [
            # Outside 'base'
            (self.PAV_LIB_DIR,
             self.PAV_ROOT_DIR/'README.md', '../../README.md'),
            # Inside 'base'
            (self.PAV_LIB_DIR,
             self.PAV_LIB_DIR/'test_config'/'variables.py',
             'test_config/variables.py'),
            # Different root.
            (self.PAV_LIB_DIR, '/etc/fstab',
             Path(*('..',)*len(self.PAV_LIB_DIR.parts) + ('/etc/fstab',))),
        ]

        for base, other, answer in tests:
            self.assertEqual(
                utils.relative_to(Path(other), Path(base)),
                Path(answer))

    def test_repair_symlinks(self):
        """Check symlink repairing."""

        # (File, target, answer)
        # A target of None means to create a regular file with the filename
        # as the contents.
        # An answer of None means the target won't exist.
        # An answer of '*' means we can't know the target's contents (but it
        # should exist).
        test_files = (
            ('t1/A', None, 'A'),
            ('t1/t2/B', None, 'B'),
            ('C', None, 'C'),
            ('d1/a', 't1/A', 'A'),
            ('d1/d2/b', 't1/t2/B', 'B'),
            ('c', 't1/A', 'A'),
            ('d1/d', 'C', 'C'),
            ('d1/e', 't1/E', None),
            # This should be absolute, and we can't control the contents.
            ('d1/f', '/etc/fstab', '*')
        )

        tmpdir = tempfile.mkdtemp()

        for base, target, _ in test_files:
            path = Path(tmpdir, base)
            path.parent.mkdir(parents=True, exist_ok=True)
            if target is None:
                with path.open('w') as file:
                    file.write(path.name)
            else:
                path.symlink_to(Path(tmpdir, target))

        utils.repair_symlinks(Path(tmpdir))

        for base, target, answer in test_files:
            path = Path(tmpdir, base)
            if answer is None:
                with self.assertRaises(FileNotFoundError):
                    path.open()
            elif answer == '*':
                self.assertTrue(path.resolve().exists())
            else:
                # Make sure the link isn't absolute.
                if path.is_symlink():
                    self.assertFalse(Path(os.readlink(str(path))).is_absolute())
                with path.open() as file:
                    self.assertEqual(file.read(), answer)
