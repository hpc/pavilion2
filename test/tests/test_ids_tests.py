from pavilion.unittest import PavTestCase
from pavilion.test_ids import TestID, SeriesID, GroupID


class TestIDTests(PavTestCase):

    def test_test_id_validation(self):
        """Test that validation is correctly performed for test IDs."""

        valid_ids = ("1", "test.1", "37")
        invalid_ids = ("", "0", "test.0", "-3", "all" "last", "")

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

        valid_ids = ("mygroup")
        invalid_ids = ("1", "s7", "all", "last", "test.1", "")

        for id in valid_ids:
            self.assertTrue(GroupID.is_valid_id(id))

        for id in invalid_ids:
            self.assertFalse(GroupID.is_valid_id(id))
