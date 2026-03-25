"""Counter utility for sequential integer IDs stored in a file.

Provides a simple persistent counter that writes the next integer to a file on each call to ``next()``.
"""

from pathlib import Path
from typing import Iterator


class Counter(Iterator[int]):
    """A lightweight persistent counter. It is the resposibility of the caller to implement
    correct locking behavior."""

    def __init__(self, directory: Path, next_id_fn: str = "next_id", start: int = 1):
        self._dir = directory

        if not self._dir.is_dir():
            raise FileNotFoundError(f"Directory does not exist: {self._dir}")

        # Sanitize filename – keep only the final component (no sub‑dirs)
        self._path = self._dir / next_id_fn
        self._start = start

        self._setup()

    def _setup(self) -> None:
        """Set up the next ID file, ensuring that it exists and is populated with the
        correct starting value."""
        
        if not self._path.exists():
            self._path.write_text(f"{self._start}\n", encoding="utf-8")
        else:
            self.reset()

    def __iter__(self) -> "Counter":
        return self

    def __next__(self) -> int:
        """Return the current value and advance the counter."""

        try:
            raw = self._path.read_text(encoding="utf-8").strip()
            current = int(raw)
        except (OSError, ValueError) as err:
            raise ValueError(f"Unable to read next value from {self._path}: {err}")

        next_val = current + 1
        self._path.write_text(f"{next_val}\n", encoding="utf-8")

        return current

    def reset(self) -> None:
        """Reset the counter to the start value."""

        self._path.write_text(f"{self._start}\n", encoding="utf-8")
