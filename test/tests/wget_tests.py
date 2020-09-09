from pathlib import Path
import json
import logging
import tempfile
import unittest

from pavilion import wget
from pavilion.unittest import PavTestCase
import traceback

PAV_DIR = Path(__file__).resolve().parents[2]

WGET_MISSING_LIBS = wget.missing_libs()


class TestWGet(PavTestCase):

    GET_TARGET = "https://github.com/lanl/Pavilion/raw/master/README.md"
    TARGET_HASH = '275fa3c8aeb10d145754388446be1f24bb16fb00'

    _logger = logging.getLogger(__file__)

    @unittest.skipIf(WGET_MISSING_LIBS,
                     "Missing wget libs: {}".format(WGET_MISSING_LIBS))
    def test_get(self):

        # Try to get a configuration from the testing pavilion.yaml file.
        try:
            info = wget.head(self.pav_cfg, self.GET_TARGET)
        except wget.WGetError as err:
            self.fail("Failed with: {}".format(err.args[0]))

        # Make sure we can pull basic info using an HTTP HEAD. The Etag can
        # change pretty easily; and the content-encoding may muck with the
        # length, so we can't really verify these.
        self.assertIn('Content-Length', info)
        self.assertIn('ETag', info)

        # Note that there are race conditions with this, however,
        # it is unlikely they will ever be encountered in this context.
        dest_fn = Path(tempfile.mktemp(dir='/tmp'))

        # Raises an exception on failure.
        try:
            wget.get(self.pav_cfg, self.GET_TARGET, dest_fn)
        except wget.WGetError as err:
            self.fail("Failed with: {}".format(err.args[0]))

        self.assertEqual(self.TARGET_HASH,
                         self.get_hash(dest_fn))

        dest_fn.unlink()

    @unittest.skipIf(WGET_MISSING_LIBS,
                     "Missing wget libs: {}".format(WGET_MISSING_LIBS))
    def test_update(self):

        dest_fn = Path(tempfile.mktemp(dir='/tmp'))
        info_fn = wget._get_info_fn(dest_fn)

        self.assertFalse(dest_fn.exists())
        self.assertFalse(info_fn.exists())

        # Update should get the file if it doesn't exist.
        try:
            wget.update(self.pav_cfg, self.GET_TARGET, dest_fn)
        except wget.WGetError as err:
            self.fail("Failed with: {}".format(err.args[0]))

        self.assertTrue(dest_fn.exists())
        self.assertTrue(info_fn.exists())

        # It should update the file if the info file isn't there and the
        # sizes don't match.
        ctime = dest_fn.stat().st_ctime
        with dest_fn.open('ab') as dest_file:
            dest_file.write(b'a')
        info_fn.unlink()
        try:
            wget.update(self.pav_cfg, self.GET_TARGET, dest_fn)
        except wget.WGetError as err:
            self.fail("Failed with: {}".format(err.args[0]))
        new_ctime = dest_fn.stat().st_ctime
        self.assertNotEqual(new_ctime, ctime)
        ctime = new_ctime

        # We'll muck up the info file data, to force an update.
        db_data = {
            'ETag': 'nope',
            'Content-Length': '-1'
        }
        with info_fn.open('w') as info_file:
            json.dump(db_data, info_file)
        try:
            wget.update(self.pav_cfg, self.GET_TARGET, dest_fn)
        except wget.WGetError as err:
            self.fail("Failed with: {}".format(err.args[0]))
        new_ctime = dest_fn.stat().st_ctime
        self.assertNotEqual(new_ctime, ctime)

        dest_fn.stat()
        info_fn.stat()
