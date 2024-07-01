"""Test directory database operations."""

import io
import json
import shutil
from pathlib import Path
from typing import Dict

from pavilion import dir_db
from pavilion import unittest
from pavilion.filters import AttributeGetter


def entry_transform(path: Path) -> Dict:
    """Our entires are some json written to the data file. Just load it."""
    with open((path/'data').as_posix()) as file:
        return AttributeGetter(json.load(file))


class DirDBTests(unittest.PavTestCase):

    def test_index(self):
        """Check the indexing code."""
        index_path = self.pav_cfg.working_dir/'test_index'  # type: Path
        shutil.rmtree(index_path, ignore_errors=True)
        index_path.mkdir()

        entries = {}
        for i in range(20):
            entries[i] = self._make_entry(index_path, i,
                                          # Every entry divisible by five will
                                          # be incomplete
                                          complete=bool(i % 5))

        output = io.StringIO()

        idx = dir_db.index(
            self.pav_cfg,
            id_dir=index_path,
            idx_name='test',
            transform=entry_transform,
            verbose=output)

        self.assertEqual(set(idx.keys()), set(entries.keys()),
                         msg="Errors: \n{}".format(output.getvalue()))
        for key in idx:
            self.assertEqual(idx[key], entries[key],
                             msg="Errors: \n{}".format(output.getvalue()))

        for i in 3, 6, 9:
            path = index_path/str(i)
            shutil.rmtree(path.as_posix())
            del entries[i]

        idx = dir_db.index(
            self.pav_cfg,
            id_dir=index_path,
            idx_name='test',
            refresh_period=0,
            transform=entry_transform)

        self.assertEqual(set(idx.keys()), set(entries.keys()),
                         msg="Errors: \n{}".format(output.getvalue()))
        for key in idx:
            self.assertEqual(idx[key], entries[key])

        # Make sure these new entries get picked up.
        for i in 43, 57, 28:
            entries[i] = self._make_entry(index_path, i)

        # The entry should be updated for these incomplete items.
        entries[5] = self._make_entry(index_path, 5, d=1)
        entries[10] = self._make_entry(index_path, 10, complete=False, d=1)
        # This is already complete, so the entry should never be updated.
        self._make_entry(index_path, 11, d=1)

        idx = dir_db.index(
            self.pav_cfg,
            id_dir=index_path,
            idx_name='test',
            refresh_period=0,
            transform=entry_transform)

        self.assertEqual(set(idx.keys()), set(entries.keys()))
        for key in idx:
            self.assertEqual(idx[key], entries[key])

        shutil.rmtree(index_path.as_posix())

    def _make_entry(self, index_path, id_, complete=True, d=0):
        value = {'a': id_ * 2,
                 'id': id_,
                 'b': 's_' * id_,
                 '3':   bool(id_ % 2),
                 'd': d,
                 'complete': complete}

        key = str(id_)
        path = index_path / key
        path.mkdir(exist_ok=True)
        with (path / 'data').open('w') as data_file:
            json.dump(value, data_file)

        return value
