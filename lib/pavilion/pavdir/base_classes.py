from abc import ABC
from os import PathLike
from pathlib import Path, PosixPath
from typing import Any

# TODO: Leave comments about why we're using PosixPath rather than Path and why we're using
# __new__ instead of __init__
class PavDirectory(PosixPath, ABC):
    def _canonical_path(self) -> str:
        return self.resolve().as_posix()

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented

        return self._canonical_path() == other._canonical_path()

    def __hash__(self) -> int:
        return hash(self._canonical_path())

    def __truediv__(self, other: PathLike) -> Path:
        # Return a PosixPath object rather than a PavDirectory
        return Path(super().__truediv__(other))
