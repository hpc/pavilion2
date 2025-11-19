import uuid

from pavilion.unittest import PavTestCase
from pavilion.test_ids import TestID, SeriesID, GroupID, TestRange, SeriesRange


class TestIDTests(PavTestCase):

    def test_test_id_validation(self):
        """Test that validation is correctly performed for test IDs."""

        valid_ids = ("1", "s2.1", "37", uuid.uuid4().hex)
        invalid_ids = ("", "test.0", "-3", "all" "last", "")

        for id in valid_ids:
            self.assertTrue(TestID.is_valid_id(id))

        for id in invalid_ids:
            self.assertFalse(TestID.is_valid_id(id))

    def test_series_id_validation(self):
        """Test that validation is correctly performed for series IDs."""

        valid_ids = ("s1", "s365", "all", "last")
        invalid_ids = ("1", "s0", "s-5", "foo", "sfoo", "")

        for id in valid_ids:
            self.assertTrue(SeriesID.is_valid_id(id))

        for id in invalid_ids:
            self.assertFalse(SeriesID.is_valid_id(id))

    def test_group_id_validation(self):
        """Test that validation is correctly performed for group IDs."""

        valid_ids = ("mygroup",)
        invalid_ids = ("1", "s7", "all", "last", "s2.1", "123abc", "-as3", "a b")

        for id in valid_ids:
            self.assertTrue(GroupID.is_valid_id(id))

        for id in invalid_ids:
            self.assertFalse(GroupID.is_valid_id(id))

    def test_test_range_expansion(self):
        """Test that test ID ranges are correctly expanded into sequences of test IDs."""

        ranges = ("1-2", "1-1")
        expected = ([TestID("1"), TestID("2")], [TestID("1")], [])

        for i, rng in enumerate(ranges):
            self.assertEqual(TestRange.from_str(rng).expand(), expected[i])

        with self.assertRaises(ValueError):
            TestRange.from_str("2-1")

    def test_series_range_expansion(self):
        """Test that series ID ranges are correctly expanded into sequences of series IDs."""

        ranges = ("s1-s2", "s1-s1")
        expected = ([SeriesID("s1"), SeriesID("s2")], [SeriesID("s1")], [])

        for i, rng in enumerate(ranges):
            self.assertEqual(SeriesRange.from_str(rng).expand(), expected[i])

        with self.assertRaises(ValueError):
            SeriesRange.from_str("s2-s1")
