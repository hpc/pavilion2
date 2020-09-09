"""Tests for various utils functions."""

import datetime as dt
import os
import tempfile
from pathlib import Path

from pavilion import unittest
from pavilion import utils


class UtilsTests(unittest.PavTestCase):

    def test_hr_cutoff(self):
        """Check hr_cutoff_to_datetime function."""

        now = dt.datetime.now()
        examples = {
            '2020': dt.datetime(2020, 1, 1),
            '2019-3': dt.datetime(2019, 3, 1),
            '2009-04-9': dt.datetime(2009, 4, 9),
            '1999-05-10 10': dt.datetime(1999, 5, 10, 10),
            '1989-06-11T11:9': dt.datetime(1989, 6, 11, 11, 9),
            '1979-07-12 12:10:9': dt.datetime(1979, 7, 12, 12, 10, 9),
            '1969-08-13T13:11:10': dt.datetime(1969, 8, 13, 13, 11, 10),
            '5second': now - dt.timedelta(seconds=5),
            '9 minutes': now - dt.timedelta(minutes=9),
            '11.5   hours': now - dt.timedelta(hours=11.5),
            '31    day': now - dt.timedelta(days=31),
            '14     week': now - dt.timedelta(weeks=14),
            '13      month': now - dt.timedelta(days=13 * 365.25/12),
            '14       year': now - dt.timedelta(days=14 * 365.25),
        }

        for example, answer in examples.items():
            self.assertEqual(
                utils.hr_cutoff_to_datetime(example, _now=now),
                answer,
                msg="Parsing '{}' failed.".format(example)
            )

        bad_examples = [
            '2019-3 12',  # You can only leave out values right-to-left
            '2019-3-4  12',  # Only one in-between char allowed.
            '2019-3-4Q11',  # Only 'T' or space allowed.
            '2019-3-4 5:6:77',  # Outside limits
            '1 blargl',  # No such time unit.
            'weeks'  # No time amount
        ]

        for example in bad_examples:
            with self.assertRaises(ValueError):
                utils.hr_cutoff_to_datetime(example)


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
