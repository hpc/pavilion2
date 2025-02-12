from pavilion.unittest import PavTestCase
from pavilion.test_ids import *

class TestIDTests(PavTestCase):

    def test_str(self):
        """Test that ID objects convert to the correct strings."""

        tid = TestID("foo")
        
        self.assertEqual(str(tid), "foo")

        sid = SeriesID("s5")

        self.assertEqual(str(sid), "s5")

    def test_valid_id(self):
        """Test that the ID objects correctly validate IDs."""

        self.assertTrue(TestID.is_valid_id("1"))
        self.assertTrue(TestID.is_valid_id("foo.bar"))
        self.assertFalse(TestID.is_valid_id("foobar"))
        self.assertFalse(TestID.is_valid_id("-7"))
        self.assertFalse(TestID.is_valid_id("0"))
        self.assertFalse(TestID.is_valid_id("s1"))
        self.assertFalse(TestID.is_valid_id(""))

        self.assertTrue(SeriesID.is_valid_id("s1"))
        self.assertTrue(SeriesID.is_valid_id("all"))
        self.assertTrue(SeriesID.is_valid_id("last"))
        self.assertFalse(SeriesID.is_valid_id("1"))
        self.assertFalse(SeriesID.is_valid_id("sh"))
        self.assertFalse(SeriesID.is_valid_id("s0"))
        self.assertFalse(SeriesID.is_valid_id("s-1"))
        self.assertFalse(SeriesID.is_valid_id(""))

        self.assertTrue(GroupID.is_valid_id("foo"))
        self.assertFalse(GroupID.is_valid_id("foo.bar"))
        self.assertFalse(GroupID.is_valid_id("1"))
        self.assertFalse(GroupID.is_valid_id("s1"))
        self.assertFalse(GroupID.is_valid_id(""))

        self.assertTrue(TestRange.is_valid_range_str("1-3"))
        self.assertTrue(TestRange.is_valid_range_str("1-1"))
        self.assertFalse(TestRange.is_valid_range_str("foo"))
        self.assertFalse(TestRange.is_valid_range_str(""))
        self.assertFalse(TestRange.is_valid_range_str("1"))
        self.assertFalse(TestRange.is_valid_range_str("-"))
        self.assertFalse(TestRange.is_valid_range_str("1-"))
        self.assertFalse(TestRange.is_valid_range_str("0-2"))
        self.assertFalse(TestRange.is_valid_range_str("2-1"))
        self.assertFalse(TestRange.is_valid_range_str("-3-1"))

        self.assertTrue(SeriesRange.is_valid_range_str("s1-s3"))
        self.assertTrue(SeriesRange.is_valid_range_str("s1-s1"))
        self.assertFalse(SeriesRange.is_valid_range_str("s"))
        self.assertFalse(SeriesRange.is_valid_range_str(""))
        self.assertFalse(SeriesRange.is_valid_range_str("1"))
        self.assertFalse(SeriesRange.is_valid_range_str("s1"))
        self.assertFalse(SeriesRange.is_valid_range_str("-"))
        self.assertFalse(SeriesRange.is_valid_range_str("s1-"))
        self.assertFalse(SeriesRange.is_valid_range_str("s0-s2"))
        self.assertFalse(SeriesRange.is_valid_range_str("s0-2"))
        self.assertFalse(SeriesRange.is_valid_range_str("s2-s1"))
        self.assertFalse(SeriesRange.is_valid_range_str("s-3-s1"))
