import shutil
import tempfile
from pathlib import Path
import multiprocessing
import os

from pavilion.unittest import PavTestCase
from pavilion.counter import SeriesIDCounter, TestIDCounter
from pavilion.test_ids import SeriesID, TestID


class CounterTests(PavTestCase):
    """Tests for the SeriesIDCounter and TestIDCounter utilities."""

    def setUp(self):
        super().set_up()
        # Create temporary directories for series and test runs.
        self._tmp_dir = Path(tempfile.mkdtemp())
        self.series_dir = self._tmp_dir / "series"
        self.series_dir.mkdir()
        self.test_run_dir = self._tmp_dir / "test_runs"
        self.test_run_dir.mkdir()

    def tearDown(self):
        # Clean up temporary directory.
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        super().tear_down()

    def test_series_id_counter_missing_dir(self):
        """Initializing SeriesIDCounter with a non‑existent directory should raise FileNotFoundError."""

        missing_dir = self._tmp_dir / "no_such_dir"

        with self.assertRaises(FileNotFoundError):
            SeriesIDCounter(missing_dir)

    def test_series_id_counter_initializes_file(self):
        """SeriesIDCounter should create a next_id file with the start value when it does not exist."""

        counter = SeriesIDCounter(self.series_dir, start_id=SeriesID("s5"))
        next_id_path = self.series_dir / "next_id"

        self.assertTrue(next_id_path.is_file())
        self.assertEqual(next_id_path.read_text().strip(), "s5")

    def test_series_id_counter_next_advances(self):
        """__next__ should return the current SeriesID and write the next one to the file.
        It should also skip IDs that already have a directory with the numeric name.
        """

        # Pre‑create a directory named '5' to force the counter to skip it.
        (self.series_dir / "5").mkdir()
        counter = SeriesIDCounter(self.series_dir, start_id=SeriesID("s5"))

        # First call should skip the existing '5' and return s6, writing s7.
        sid = next(counter)

        self.assertIsInstance(sid, SeriesID)
        self.assertEqual(str(sid), "s6")
        self.assertEqual((self.series_dir / "next_id").read_text().strip(), "s7")

    def test_test_id_counter_missing_dir(self):
        """Initializing TestIDCounter with a non‑existent test run directory should raise FileNotFoundError."""

        missing_dir = self._tmp_dir / "no_test_dir"

        with self.assertRaises(FileNotFoundError):
            TestIDCounter(SeriesID("s1"), missing_dir)

    def test_test_id_counter_next_skips_existing(self):
        """TestIDCounter.__next__ should skip IDs that already have a directory."""

        # Create a directory for an existing test ID.
        existing = self.test_run_dir / "s1.1"
        existing.mkdir()
        counter = TestIDCounter(SeriesID("s1"), self.test_run_dir, start_id=1)

        # The first generated ID should be s1.2 because s1.1 exists.
        tid = next(counter)
        self.assertIsInstance(tid, TestID)
        self.assertEqual(str(tid), "s1.2")

    def test_series_id_counter_locking(self):
        """Ensure that concurrent access using the lock prevents duplicate IDs.

        This test creates two separate SeriesIDCounter instances pointing to the same
        directory and invokes ``next`` on each in separate processes. The lock file
        should serialize access so that the generated IDs are distinct.
        """

        # Helper function executed in a subprocess.
        def worker(tmp_dir, result_queue):
            counter = SeriesIDCounter(tmp_dir)
            sid = next(counter)
            result_queue.put(str(sid))

        # Use a multiprocessing.Queue to collect results.
        result_queue = multiprocessing.Queue()
        
        # Start two processes that both use the same directory.
        p1 = multiprocessing.Process(target=worker, args=(self.series_dir, result_queue))
        p2 = multiprocessing.Process(target=worker, args=(self.series_dir, result_queue))
        p1.start()
        p2.start()
        p1.join()
        p2.join()

        ids = []

        while not result_queue.empty():
            ids.append(result_queue.get())

        # There should be exactly two IDs and they should be different.
        self.assertEqual(len(ids), 2)
        self.assertNotEqual(ids[0], ids[1])
