from hashlib import sha1
import dbm
import logging
import os
import tempfile

from pavilion import wget
from pavilion.unittest import PavTestCase

PAV_DIR = os.path.realpath(__file__)
for i in range(3):
    PAV_DIR = os.path.dirname(PAV_DIR)


def get_hash(fn):
    with open(fn, 'rb') as file:
        sha = sha1()
        sha.update(file.read())
        return sha.hexdigest()


class TestWGet(PavTestCase):

    GET_TARGET = "https://github.com/lanl/Pavilion/raw/2.0/README.md"
    LOCAL_TARGET = os.path.join(PAV_DIR, 'README.md')

    _logger = logging.getLogger(__file__)

    def test_get(self):

        # Try to get a configuration from the testing pavilion.yaml file.
        info = wget.head(self.pav_cfg, self.GET_TARGET)

        # Make sure we can pull basic info using an HTTP HEAD. The Etag can
        # change pretty easily; and the content-encoding may muck with the
        # length, so we can't really verify these.
        self.assertIn('Content-Length', info)
        self.assertIn('ETag', info)

        # Note that there are race conditions with this, however,
        # it is unlikely they will ever be encountered in this context.
        dest_fn = tempfile.mktemp(dir='/tmp')

        # Raises an exception on failure.
        wget.get(self.pav_cfg, self.GET_TARGET, dest_fn)

        self.assertEqual(get_hash(self.LOCAL_TARGET), get_hash(dest_fn))

        os.unlink(dest_fn)

    def test_update(self):

        dest_fn = tempfile.mktemp(dir='/tmp')
        info_fn = '{}.info'.format(dest_fn)

        self.assertFalse(os.path.exists(dest_fn))
        self.assertFalse(os.path.exists(info_fn))

        # Update should get the file if it doesn't exist.
        wget.update(self.pav_cfg, self.GET_TARGET, dest_fn)
        self.assertTrue(os.path.exists(dest_fn))
        self.assertTrue(os.path.exists(info_fn))

        # It should update the file if the info file isn't there and the
        # sizes don't match.
        ctime = os.stat(dest_fn).st_ctime
        with open(dest_fn, 'ab') as dest_file:
            dest_file.write(b'a')
        os.unlink(info_fn)
        wget.update(self.pav_cfg, self.GET_TARGET, dest_fn)
        new_ctime = os.stat(dest_fn).st_ctime
        self.assertNotEqual(new_ctime, ctime)
        ctime = new_ctime

        # We'll muck up the info file data, to force an update.
        with dbm.open(info_fn, 'w') as db:
            db['ETag'] = 'nope'
            db['Content-Length'] = '-1'
        wget.update(self.pav_cfg, self.GET_TARGET, dest_fn)
        new_ctime = os.stat(dest_fn).st_ctime
        self.assertNotEqual(new_ctime, ctime)

        os.unlink(dest_fn)
        os.unlink(info_fn)
