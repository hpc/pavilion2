"""Tests for various utils functions."""

import datetime as dt
import subprocess as sp
import getpass
import os
import tempfile
import pwd
from pathlib import Path
from unittest import mock
from types import SimpleNamespace

from pavilion import utils
from pavilion.cmd_utils import list_files
from pavilion.unittest import PavTestCase


class UtilsTests(PavTestCase):

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
                utils.hr_cutoff_to_ts(example, _now=now),
                answer.timestamp(),
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
                utils.hr_cutoff_to_ts(example)

    def test_owner(self):
        """Check that the owner function works."""

        path = Path(tempfile.mktemp())

        with path.open('w') as file:
            file.write('hi there')

        self.assertEqual(utils.owner(path), getpass.getuser())

        # Simulate a file owned by a UID that has no corresponding user entry
        with mock.patch.object(Path, "stat", return_value=SimpleNamespace(st_uid=12341)):
            with mock.patch.object(pwd, "getpwuid", side_effect=KeyError):
                self.assertEqual(utils.owner(path), "<unknown user '12341'>")

    def test_relative_to(self):
        """Check relative path calculations."""

        # base, target, answer
        tests = [
            # Outside 'base'
            (self.PAV_LIB_DIR / "pavilion",
             self.PAV_ROOT_DIR/'README.md', '../../README.md'),
            # Inside 'base'
            (self.PAV_LIB_DIR / "pavilion",
             self.PAV_LIB_DIR/ "pavilion" / 'test_config' / 'variables.py',
             'test_config/variables.py'),
            # Different root.
            (self.PAV_LIB_DIR / "pavilion", '/etc/fstab',
             Path(*('..',)*len((self.PAV_LIB_DIR / "pavilion").parts) + ('/etc/fstab',))),
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

    def test_copytree_dotfiles(self):
        """Check that copytree copies dotfiles."""

        with tempfile.TemporaryDirectory() as dir:
            src = Path(dir) / "src"
            dest = Path(dir) / "dest"
            dotfile = src / ".dotfile"

            src.mkdir()
            dotfile.touch()

            utils.copytree(src, dest)

            names = (map(lambda x: x.name, dest.iterdir()))
            self.assertIn(".dotfile", names)

    def test_copytree_resolved(self):
        examples = [
            {
                "copy_root": "foo",
                "files": [
                    {"name": "foo", "dir": True, "target": None},
                    {"name": "bar", "dir": False, "target": None},
                    {"name": "foo/baz", "dir": False, "target": "bar"},
                ],
                "expected": [
                    {"name": "baz", "dir": False, "target": None},
                ]
            },
            {
                "copy_root": None,
                "files": [
                    {"name": "foo", "dir": False, "target": "bar"},
                    {"name": "bar", "dir": False, "target": "foo"},
                ],
                "expected": []
            },
            {
                "copy_root": "foo",
                "files": [
                   {"name": "foo", "dir": True, "target": None},
                   {"name": "foo/bar", "dir": False, "target": "foobar"},
                   {"name": "foo/baz", "dir": False, "target": None},
                   {"name": "foobar", "dir": False, "target": "foo/baz"}
                ],
                "expected": [
                   {"name": "bar", "dir": False, "target": "baz"},
                   {"name": "baz", "dir": False, "target": None},
                ]
            },
            {
                "copy_root": None,
                "files": [
                   {"name": "foo", "dir": True, "target": None},
                   {"name": "bar", "dir": False, "target": None},
                   {"name": "foo/baz", "dir": False, "target": "bar"},
                   {"name": "foobar", "dir": False, "target": "bar"},
                ],
                "expected": [
                   {"name": "foo", "dir": True, "target": None},
                   {"name": "bar", "dir": False, "target": None},
                   {"name": "foo/baz", "dir": False, "target": "bar"},
                   {"name": "foobar", "dir": False, "target": "bar"},
                ]
            },
            {
                "copy_root": "foo",
                "files": [
                   {"name": "foo", "dir": True, "target": None},
                   {"name": "bar", "dir": False, "target": None},
                   {"name": "foo/baz", "dir": False, "target": "bar"},
                   {"name": "foo/foobar", "dir": False, "target": "bar"},
                ],
                "expected": [
                   {"name": "baz", "dir": False, "target": None},
                   {"name": "foobar", "dir": False, "target": "baz"},
                ]
            }
        ]

        for i, ex in enumerate(examples):
            with tempfile.TemporaryDirectory() as src:
                src = Path(src)

                with tempfile.TemporaryDirectory() as dest:
                    dest = Path(dest)

                    # Create the files.
                    for f in ex["files"]:
                        file_path = src / f["name"]

                        if f["dir"]:
                            file_path.mkdir(parents=True)
                        else:
                            if f["target"] is None:
                                file_path.touch()
                            else:
                                target_path = src / f["target"]
                                file_path.symlink_to(target_path)

                    if ex["copy_root"] is None:
                        utils.copytree_resolved(src, dest)
                    else:
                        utils.copytree_resolved(src / ex["copy_root"], dest)

                    expected = set(Path(f["name"]) for f in ex["expected"])
                    actual = set(p.relative_to(dest) for p in list_files(dest))

                    self.assertEqual(expected, actual)

                    for f in ex["expected"]:
                        for g in actual:
                            if Path(f["name"]) == g:
                                if f["target"] is None:
                                    self.assertFalse((dest / g).is_symlink())
                                else:
                                    self.assertTrue((dest / g).is_symlink())
