import os
import tempfile
from pathlib import Path

from pavilion.unittest import PavTestCase
from pavilion.counter import Counter


class CounterTests(PavTestCase):

    def test_basic_sequence_and_reset(self):
        """Verify normal counting and reset behavior."""

        with tempfile.TemporaryDirectory() as td:
            dir_path = Path(td)
            c = Counter(dir_path)  # uses default filename "next_id"
            self.assertEqual(next(c), 1)
            self.assertEqual(next(c), 2)
            c.reset()
            self.assertEqual(next(c), 1)

    def test_custom_filename(self):
        """Counter should respect a custom filename for the ID file."""
        
        with tempfile.TemporaryDirectory() as td:
            dir_path = Path(td)
            c = Counter(dir_path, next_id_fn="my_counter")
            self.assertEqual(next(c), 1)
            # ensure file was created with custom name
            self.assertTrue(os.path.isfile(os.path.join(td, "my_counter")))

    def test_missing_directory_raises(self):
        """Initializing Counter with a non‑existent directory should raise FileNotFoundError."""

        with self.assertRaises(FileNotFoundError):
            Counter(Path("/nonexistent/path"))

    def test_invalid_file_contents(self):
        """If the counter file contains non‑integer data, next() should raise ValueError."""

        with tempfile.TemporaryDirectory() as td:
            dir_path = Path(td)
            # pre‑populate file with bad data
            bad_path = dir_path / "next_id"
            c = Counter(dir_path)

            with open(bad_path, "w", encoding="utf-8") as f:
                f.write("not_an_int\n")

            with self.assertRaises(ValueError):
                next(c)
