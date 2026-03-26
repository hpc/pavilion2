"""Counter utilities for sequential series and test IDs."""

from pathlib import Path
from typing import Iterator

from flufl.lock import Lock

from pavilion.test_ids import SeriesID, TestID


class SeriesIDCounter(Iterator[SeriesID]):
    """A file-based counter for generating series IDs."""

    LOCKFILE_FN = ".lockfile"

    def __init__(self, series_dir: Path, next_id_fn: str = "next_id",
                 start_id: SeriesID = SeriesID("s1")):
        self._dir = series_dir

        if not self._dir.is_dir():
            raise FileNotFoundError(f"Directory does not exist: {self._dir}")

        self._path = self._dir / next_id_fn
        self._start = start_id
        self._lockfile = Lock(self._dir / self.LOCKFILE_FN, lifetime=3)

        self._setup()

    def _setup(self) -> None:
        """Set up the next ID file, ensuring that it exists and is populated with the
        correct starting value. If an existing next ID file is found, the current value
        is retained."""

        with self._lockfile:
            if not self._path.exists():
                self._path.write_text(f"{self._start}\n", encoding="utf-8")

    def __iter__(self) -> "SeriesIDCounter":
        return self

    def __next__(self) -> SeriesID:
        """Return the next SeriesID and advance the counter, skipping IDs that already
        have a series directory."""

        with self._lockfile:
            try:
                raw = self._path.read_text(encoding="utf-8").strip()
                current_id = SeriesID(raw)
            except (OSError, ValueError) as err:
                raise ValueError(f"Unable to read next value from {self._path}: {err}")

            while (self._dir / str(current_id.as_int())).exists():
                current_id = current_id.next()

            self._path.write_text(f"{current_id.next()}\n", encoding="utf-8")

        return current_id

    def reset(self) -> None:
        """Reset the counter to the start value."""

        with self._lockfile:
            self._path.write_text(f"{self._start}\n", encoding="utf-8")


class TestIDCounter(Iterator[TestID]):
    """A counter for generating test IDs."""

    def __init__(self, series: SeriesID, test_run_dir: Path, start_id: int = 1):
        self._test_run_dir = test_run_dir
        self._current_id = TestID(f"{series}.{start_id}")

        if not self._test_run_dir.is_dir():
            raise FileNotFoundError(f"Directory does not exist: {self._test_run_dir}")

    def __iter__(self) -> "TestIDCounter":
        return self

    def __next__(self) -> TestID:
        """Return the next valid TestID, skipping IDs that already have a test run directory."""

        while (self._test_run_dir / str(self._current_id)).exists():
            self._current_id = self._current_id.next()

        res = self._current_id

        self._current_id = self._current_id.next()

        return res
