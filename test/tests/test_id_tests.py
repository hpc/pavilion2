from pavilion.unittest import PavTestCase
from pavilion.test_ids import *

class TestIDTests(PavTestCase):

    def test_string_conversion(self):
        """Test that ID objects convert to the correct strings."""

        tid = TestID("foo")
        
        self.assertEqual(str(tid), "foo")

        sid = SeriesID("s5")

        self.assertEqual(str(sid), "s5")

    def test_validate_id(self):
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

    def test_range_from_string(self):
        """Test that ranges are correctly create from strings."""

        self.assertEqual(TestRange.from_str("1-3"), TestRange(1, 3))
        self.assertEqual(SeriesRange.from_str("s1-s3"), SeriesRange(1, 3))

    def test_expand_range(self):
        """Test that range expansion produces the correct sequence of test or series IDs."""

        test_range = TestRange(1, 3)
        self.assertEqual(list(test_range.expand()), [TestID("1"), TestID("2"), TestID("3")])

        test_range = TestRange(1, 1)
        self.assertEqual(list(test_range.expand()), [TestID("1")])

        series_range = SeriesRange(1, 3)
        self.assertEqual(list(series_range.expand()), [SeriesID("s1"), SeriesID("s2"), SeriesID("s3")])

        series_range = SeriesRange(1, 1)
        self.assertEqual(list(series_range.expand()), [SeriesID("s1")])
